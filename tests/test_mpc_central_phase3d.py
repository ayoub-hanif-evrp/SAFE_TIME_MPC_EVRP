"""Phase 3D: distance accounting, estimation contract, predictive MPC pilot."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Decision, Visit
from safe_time_evrp.mpc_central.causal_plant import evaluate_action_scenario, expected_action_value
from safe_time_evrp.mpc_central.decision_regret import equal_allocation, paired_common_random, uniform_rollout
from safe_time_evrp.mpc_central.eval_bank import EvalBank, OfflineOracle
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork
from safe_time_evrp.mpc_central.phase3d_pilot import run_phase3d_pilot
from safe_time_evrp.validation.replay import validate_log


def test_executed_distance_nonzero_for_known_travel():
    spec = case_a_predictive_charging_fork()
    score = evaluate_action_scenario(spec, "serve_near", spec.scenarios[0], scenario_index=0)
    assert score.replay_ok
    dist_note = next(n for n in score.notes if n.startswith("executed_distance="))
    dist = float(dist_note.split("=", 1)[1])
    assert dist > 0.0
    # Arc table reconstruction matches plant score note.
    sim = FleetSimulator(spec.instance, 1)
    for cid, t in spec.base_releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    vid = next(iter(sim.vehicles))
    sim.apply_decision(
        Decision(
            0.0,
            {vid: [Visit("Near", "service")]},
            ["Near"],
            ["Near"],
            [],
            [],
            False,
            False,
            False,
            ["Near"],
            0.0,
            0.0,
            0.0,
            "t",
            {},
            [],
        )
    )
    # Force a depart by stepping until travel starts.
    for _ in range(20):
        if any(r.kind == "depart" for r in sim.log):
            break
        ev = sim.pop_event()
        if ev is None:
            break
    assert any(r.kind == "depart" for r in sim.log)
    assert executed_distance_from_log(spec.instance, sim.log) > 0.0


def test_b1_recourse_default_and_insertion_baseline_label():
    spec = case_a_predictive_charging_fork()
    b1 = evaluate_action_scenario(spec, "charge_first", spec.scenarios[1], recourse="b1_validated")
    ins = evaluate_action_scenario(spec, "charge_first", spec.scenarios[1], recourse="insertion")
    assert "recourse=b1_validated" in b1.notes
    assert "recourse=insertion" in ins.notes
    assert b1.replay_ok and ins.replay_ok


def test_sampled_expectation_no_renormalization():
    spec = case_a_predictive_charging_fork()
    bank = EvalBank(spec)
    # Only scenario 0 for charge_first; scenario 1 is much better.
    bank.evaluate("charge_first", 0)
    est = bank.sampled_expectation("charge_first", missing_fill=0.0)
    assert est is not None
    # Prior mass on scenario 0 only contributes; missing gets 0 (not renormalized to 1.0).
    p0 = spec.scenario_probs[0]
    assert abs(est - p0 * bank._cache[("charge_first", 0)].value) < 1e-9
    # Renormalization would equal the raw scenario-0 value; require they differ when p0 < 1.
    assert p0 < 1.0 - 1e-12
    assert abs(est - bank._cache[("charge_first", 0)].value) > 1e-6


def test_equal_and_crn_respect_budget():
    spec = case_a_predictive_charging_fork()
    oracle = OfflineOracle.build(spec)
    eq = equal_allocation(spec, oracle, budget=3)
    crn = paired_common_random(spec, oracle, budget=3)
    uni = uniform_rollout(spec, oracle, budget=3)
    assert eq.scenario_evals <= 3
    assert crn.scenario_evals <= 3
    assert uni.scenario_evals <= 3


def test_predictive_mpc_closed_loop_smoke():
    spec = case_a_predictive_charging_fork()
    # Tiny closed loop on case A geometry with Near released at 0.
    ctrl = CommitmentSafePredictiveMpc(
        spec.instance, horizon=80.0, n_scenarios=1, alns_iterations=8, time_limit_seconds=0.2
    )
    releases = list(spec.base_releases)
    result = run_episode(
        spec.instance,
        releases,
        fleet_size=1,
        horizon=80.0,
        max_replan_interval=10.0,
        t_max=spec.t_max,
        controller=ctrl,
    )
    report = validate_log(spec.instance, result.log)
    assert report.ok
    assert ctrl.profile.decisions >= 1
    assert result.decisions[0].notes[0] == "commitment_safe_predictive_mpc"


def test_phase3d_pilot_writes_artifact():
    art = run_phase3d_pilot(out_path=Path("docs/mpc_central/phase3d_results.json"))
    assert art["verdict"] in {"GO", "REVISE", "NO-GO"}
    assert "repaired_fork_values" in art
    assert art["fairness_summary"]["n_comparisons"] == 18
    # Distance must appear nonzero on at least one fork action scenario.
    dists = []
    for case in art["repaired_fork_values"]["cases"]:
        for _action, payload in case["actions"].items():
            for sc in payload["scenarios"]:
                dists.append(sc["executed_distance"])
    assert any(d > 0 for d in dists)
    out = Path("docs/mpc_central/phase3d_results.json")
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["verdict"] == art["verdict"]


def test_case_a_ranking_preserved_after_distance_fix():
    spec = case_a_predictive_charging_fork()
    serve, _ = expected_action_value(spec, "serve_near")
    charge, scores = expected_action_value(spec, "charge_first")
    assert charge > serve + 1e-9
    assert all(s.replay_ok for s in scores)
    assert any(float(n.split("=")[1]) > 0 for s in scores for n in s.notes if n.startswith("executed_distance="))
