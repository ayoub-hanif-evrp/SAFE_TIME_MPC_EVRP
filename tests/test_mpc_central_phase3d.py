"""Phase 3D: distance accounting, estimation contract, predictive MPC pilot."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Decision, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, TrainDemandAtom, build_anonymous_scenarios
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.causal_plant import evaluate_action_scenario, expected_action_value
from safe_time_evrp.mpc_central.decision_regret import equal_allocation, paired_common_random, uniform_rollout
from safe_time_evrp.mpc_central.eval_bank import EvalBank, OfflineOracle
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork
from safe_time_evrp.mpc_central.fulfillment_audit import audit_frontier_unfulfilled
from safe_time_evrp.mpc_central.phase3d_pilot import run_au_residual_audit, run_phase3d_pilot
from safe_time_evrp.mpc_central.phase3d_splits import (
    DEV_CASE_IDS,
    HOLDOUT_CASE_IDS,
    TRAIN_CASE_IDS,
    fit_train_forecast,
    holdout_cases,
    split_manifest,
)
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, seed_simulator_from_observation
from safe_time_evrp.validation.replay import validate_log


def test_executed_distance_nonzero_for_known_travel():
    spec = case_a_predictive_charging_fork()
    score = evaluate_action_scenario(spec, "serve_near", spec.scenarios[0], scenario_index=0)
    assert score.replay_ok
    dist_note = next(n for n in score.notes if n.startswith("executed_distance="))
    dist = float(dist_note.split("=", 1)[1])
    assert dist > 0.0
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
    bank.evaluate("charge_first", 0)
    est = bank.sampled_expectation("charge_first", missing_fill=0.0)
    assert est is not None
    p0 = spec.scenario_probs[0]
    assert abs(est - p0 * bank._cache[("charge_first", 0)].value) < 1e-9
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


def test_causal_scenario_rollout_from_observation():
    spec = case_a_predictive_charging_fork()
    sim = FleetSimulator(spec.instance, 1)
    for cid, t in spec.base_releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    vid = obs.vehicles[0].id
    cand = Decision(
        time=obs.time,
        routes={vid: [Visit("Near", "service")]},
        accepted=["Near"],
        newly_accepted=["Near"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["Near"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    model = ArrivalForecast(
        train_atoms=(TrainDemandAtom(8.0, 0.0, 1.0, 1.0, 5.0, 80.0),),
        train_interarrival_mean=4.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=1, seed=stable_seed("p3d", "r"))
    mean_v, scores = expected_rollout_value(
        spec.instance,
        obs,
        cand,
        fcst.scenarios,
        horizon=80.0,
        max_events=200,
    )
    assert len(scores) == 1
    assert "causal_scenario_rollout" in scores[0].notes
    assert scores[0].executed_distance >= 0.0
    assert isinstance(mean_v, float)
    forked = seed_simulator_from_observation(spec.instance, obs)
    assert abs(forked.time - obs.time) <= 1e-12


def test_train_dev_holdout_disjoint_and_forecast_train_only():
    manifest = split_manifest()
    assert set(TRAIN_CASE_IDS).isdisjoint(DEV_CASE_IDS)
    assert set(TRAIN_CASE_IDS).isdisjoint(HOLDOUT_CASE_IDS)
    assert set(DEV_CASE_IDS).isdisjoint(HOLDOUT_CASE_IDS)
    assert manifest["holdout_status"] == "untouched"
    fcst = fit_train_forecast(n_scenarios=2, customers_per_scenario=1, seed=1)
    assert fcst.train_atoms
    assert fcst.scenarios
    # Holdout case must not appear in train atom geometry ids (anonymous scenarios only).
    holdout = holdout_cases()[0]
    holdout_ids = set(holdout.instance.customer_ids())
    for scenario in fcst.scenarios:
        for item in scenario:
            assert item.customer_id not in holdout_ids


def test_predictive_mpc_closed_loop_uses_causal_rollouts():
    spec = case_a_predictive_charging_fork()
    model = ArrivalForecast(
        train_atoms=(TrainDemandAtom(8.0, 0.0, 1.0, 1.0, 5.0, 80.0),),
        train_interarrival_mean=4.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=1, seed=3)
    ctrl = CommitmentSafePredictiveMpc(
        spec.instance,
        horizon=80.0,
        forecast=fcst,
        n_scenarios=1,
        alns_iterations=6,
        time_limit_seconds=0.5,
        rollout_max_events=120,
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
    assert "causal_rollouts=1" in result.decisions[0].notes
    assert ctrl.profile.causal_rollouts >= 1


def test_au_residual_smoke_distinguishes_cutoff():
    art = audit_frontier_unfulfilled(limit=2, iterations=15)
    assert art["n_audited"] == 2
    for row in art["rows"]:
        if row["accepted_unfulfilled_count"] > 0:
            assert "residual_check" in row
            assert "cutoff_vs_infeasibility" in row


def test_phase3d_pilot_writes_artifact():
    # Fast path: skip full 31-row AU inside unit test (generated separately / in __main__).
    art = run_phase3d_pilot(out_path=Path("docs/mpc_central/phase3d_results.json"), run_au_audit=False)
    assert art["verdict"] in {"GO", "REVISE", "NO-GO"}
    assert art["splits"]["holdout_status"] == "untouched"
    assert art["closed_loop"]["holdout_untouched"] == list(HOLDOUT_CASE_IDS)
    assert any(
        r["controllers"]["predictive_uniform"].get("causal_rollout_decisions", 0) >= 1
        for r in art["closed_loop"]["rows"]
    )
    dists = []
    for case in art["repaired_fork_values"]["cases"]:
        for _action, payload in case["actions"].items():
            for sc in payload["scenarios"]:
                dists.append(sc["executed_distance"])
    assert any(d > 0 for d in dists)
    loaded = json.loads(Path("docs/mpc_central/phase3d_results.json").read_text(encoding="utf-8"))
    assert loaded["verdict"] == art["verdict"]


def test_case_a_ranking_preserved_after_distance_fix():
    spec = case_a_predictive_charging_fork()
    serve, _ = expected_action_value(spec, "serve_near")
    charge, scores = expected_action_value(spec, "charge_first")
    assert charge > serve + 1e-9
    assert all(s.replay_ok for s in scores)
    assert any(float(n.split("=")[1]) > 0 for s in scores for n in s.notes if n.startswith("executed_distance="))


def test_full_au_residual_artifact_or_generate():
    """Ensure the committed AU residual artifact exists with full frontier coverage."""
    path = Path("docs/mpc_central/phase3d_au_residual.json")
    if not path.exists():
        run_au_residual_audit(iterations=40, out_path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["n_audited"] == data["n_source_au_rows"]
    assert data["n_audited"] >= 30
    assert "cutoff_with_feasible_continuation" in data
    assert "residual_feasible_true" in data
