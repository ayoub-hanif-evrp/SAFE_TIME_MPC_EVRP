"""Phase 3C: budget honesty, order falsification, commitment validity."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Anchor, Decision, Visit
from safe_time_evrp.mpc_central.causal_plant import action_to_decision, expected_action_value
from safe_time_evrp.mpc_central.decision_regret import adaptive_mpc, run_fairness_suite, uniform_rollout
from safe_time_evrp.mpc_central.eval_bank import EvalBank, OfflineOracle
from safe_time_evrp.mpc_central.forks import (
    case_a_predictive_charging_fork,
    case_c_commitment_plus_uncertain_demand,
    with_action_order,
)
from safe_time_evrp.mpc_central.fulfillment_audit import audit_frontier_unfulfilled


def test_eval_bank_counts_unique_rollouts_only():
    spec = case_a_predictive_charging_fork()
    bank = EvalBank(spec)
    bank.evaluate("serve_near", 0)
    bank.evaluate("serve_near", 0)  # cache hit
    bank.evaluate("charge_first", 1)
    assert bank.n_evals == 2


def test_uniform_does_not_exceed_budget_or_hidden_evals():
    spec = case_a_predictive_charging_fork()
    oracle = OfflineOracle.build(spec)
    res = uniform_rollout(spec, oracle, budget=3)
    assert res.scenario_evals <= 3
    assert res.scenario_evals == 3


def test_adaptive_never_calls_oracle_inside_loop():
    """Adaptive uses only EvalBank; exhaustive truth is offline for regret scoring."""
    spec = case_a_predictive_charging_fork()
    oracle = OfflineOracle.build(spec)
    before = oracle.n_oracle_evals
    res = adaptive_mpc(spec, oracle, budget=3)
    assert oracle.n_oracle_evals == before
    assert res.scenario_evals <= 3
    assert "no_oracle_in_loop" in res.notes


def test_reversed_candidate_order_documented_in_fairness_suite():
    report = run_fairness_suite(budgets=(3, 4), reverse_actions=True, reverse_scenarios=True)
    assert report["verdict"] in {"GO", "REVISE", "NO-GO"}
    # The known Phase-3B artifact: budget-3 wins vanish under reverse order.
    assert any("reversed candidate order" in n for n in report["fragile_notes"]) or report["adaptive_better"] == 0
    out = Path("docs/mpc_central/phase3c_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_case_c_reload_route_is_nominally_feasible():
    """Capacity-3 reload proof (audit concern) — still feasible when capacity allows separate loads."""
    from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance

    vehicle = VehicleType(100.0, 3.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 400), 0),
        Node("S", NodeKind.CHARGER, 1, 1, 0, TimeWindow(0, 400), 0),
        Node("Must", NodeKind.CUSTOMER, 4, 0, 2, TimeWindow(0, 60), 2),
        Node("Now", NodeKind.CUSTOMER, 22, 0, 2, TimeWindow(0, 90), 10),
    ]
    inst = build_euclidean_instance(
        "reload_proof",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="phase3c",
        assumptions=(),
    )
    visits = [Visit("Must", "service"), Visit("D", "reload"), Visit("Now", "service")]
    res = evaluate_route(inst, Anchor("D", 0.0, 100.0, 0.0, frozenset()), visits, NominalLinearEnergy())
    assert res.feasible
    assert set(res.served) == {"Must", "Now"}


def test_case_c_accept_validated_and_reject_preferred_in_expectation():
    spec = case_c_commitment_plus_uncertain_demand()
    acc, acc_s = expected_action_value(spec, "accept_now_after_must")
    rej, rej_s = expected_action_value(spec, "reject_now_serve_must")
    assert all(s.replay_ok for s in (*acc_s, *rej_s))
    assert all("Must" in s.completed for s in (*acc_s, *rej_s))
    assert rej > acc + 1e-9
    # validate_continuation passes for accept
    sim = FleetSimulator(spec.instance, 1)
    for cid, t in spec.base_releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    vid = next(iter(sim.vehicles))
    sim.apply_decision(
        Decision(
            0.0,
            {vid: []},
            list(spec.prior_accepted),
            list(spec.prior_accepted),
            [],
            [],
            False,
            False,
            False,
            [],
            0.0,
            0.0,
            0.0,
            "seed",
            {},
            [],
        )
    )
    d = action_to_decision(spec, "accept_now_after_must", vehicle_id=vid)
    val = validate_continuation(spec.instance, sim.observation(), d.routes, require_new=frozenset(d.newly_accepted))
    assert val.ok


def test_order_permutation_changes_budget3_winner_pair():
    spec = case_a_predictive_charging_fork()
    oracle = OfflineOracle.build(spec)
    base_u = uniform_rollout(spec, oracle, budget=3)
    base_a = adaptive_mpc(spec, oracle, budget=3)
    rev = with_action_order(spec, tuple(reversed(spec.candidate_actions)))
    oracle_r = OfflineOracle.build(rev)
    rev_u = uniform_rollout(rev, oracle_r, budget=3)
    rev_a = adaptive_mpc(rev, oracle_r, budget=3)
    # Document: at least one of base vs rev adaptive/uniform relationship differs, or both tie after reverse.
    base_win = base_a.regret + 1e-9 < base_u.regret
    rev_win = rev_a.regret + 1e-9 < rev_u.regret
    assert base_win  # adaptive helps in original order at budget 3
    assert not rev_win  # vanishes when order reversed (falsification)


def test_fulfillment_uses_termination_reason():
    art = audit_frontier_unfulfilled(limit=2, iterations=15)
    assert art["n_audited"] == 2
    for row in art["rows"]:
        assert "termination_reason" in row
        assert row["termination_reason"] != "unspecified" or row["label"].startswith("residual")
