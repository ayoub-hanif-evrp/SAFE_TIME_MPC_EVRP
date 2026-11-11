"""Phase 3B: causal plant validity, decision regret, noninterference."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    TrainDemandAtom,
    build_anonymous_scenarios,
    visible_forecast,
)
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.causal_plant import (
    clairvoyant_route_would_leak,
    early_service_before_release,
    expected_action_value,
)
from safe_time_evrp.mpc_central.decision_regret import run_decision_regret_gate
from safe_time_evrp.mpc_central.forks import (
    case_a_predictive_charging_fork,
    case_b_irreversible_admission_fork,
    case_c_commitment_plus_uncertain_demand,
)
from safe_time_evrp.mpc_central.fulfillment_audit import audit_frontier_unfulfilled
from safe_time_evrp.testbed.constructor import make_observation


def test_plant_case_a_prediction_improves_expected_value():
    spec = case_a_predictive_charging_fork()
    serve, serve_scores = expected_action_value(spec, "serve_near")
    charge, charge_scores = expected_action_value(spec, "charge_first")
    assert all(s.replay_ok for s in (*serve_scores, *charge_scores))
    assert charge > serve + 1e-9
    assert charge_scores[1].completed == ("Far", "Near")
    assert "Far" not in serve_scores[1].completed


def test_plant_case_b_reject_beats_accept_in_expectation():
    spec = case_b_irreversible_admission_fork()
    acc, acc_s = expected_action_value(spec, "accept_now")
    rej, rej_s = expected_action_value(spec, "reject_now")
    assert all(s.replay_ok for s in (*acc_s, *rej_s))
    assert rej > acc + 1e-9


def test_plant_case_c_commitment_reject_beats_validated_accept():
    spec = case_c_commitment_plus_uncertain_demand()
    acc, acc_s = expected_action_value(spec, "accept_now_after_must")
    rej, rej_s = expected_action_value(spec, "reject_now_serve_must")
    assert all(s.replay_ok for s in (*acc_s, *rej_s))
    assert all("Must" in s.completed for s in (*acc_s, *rej_s))
    assert rej > acc + 1e-9


def test_adversarial_clairvoyant_leak_is_detectable():
    spec = case_b_irreversible_admission_fork()
    assert clairvoyant_route_would_leak(spec) is True


def test_causal_recourse_does_not_serve_before_release():
    spec = case_b_irreversible_admission_fork()
    sc = spec.scenarios[1]
    bad = early_service_before_release(spec, "reject_now", sc)
    assert bad == []


def test_decision_regret_gate_writes_phase3b_snapshot():
    report = run_decision_regret_gate(budgets=(3, 6))
    assert report["verdict"] in {"GO_PROTOTYPE", "GO", "REVISE", "NO-GO"}
    out = Path("docs/mpc_central/phase3b_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_hidden_eval_mutation_does_not_change_visible_forecast():
    model = ArrivalForecast(
        train_atoms=(TrainDemandAtom(2.0, 2.0, 1.0, 1.0, 1.0, 40.0),),
        train_interarrival_mean=3.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=2, seed=stable_seed("p3b", "h"))

    def env(hidden):
        from safe_time_evrp.models.instance import VehicleType, build_euclidean_instance

        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
            Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
            Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
            *hidden,
        ]
        vehicle = VehicleType(40.0, 10.0, 1.0, 0.2, 1.0, "full")
        return build_euclidean_instance("n", nodes, vehicle, source_format="t", source_name="t", assumptions=())

    ea = env([Node("H1", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(50, 120), 1)])
    eb = env([Node("HX", NodeKind.CUSTOMER, 0, 30, 1, TimeWindow(60, 90), 1)])
    oa = Observation(0.0, make_observation(ea, 1).vehicles, ("A",), (), (), (), (), ())
    ob = Observation(0.0, make_observation(eb, 1).vehicles, ("A",), (), (), (), (), ())
    assert [c.customer_id for c in visible_forecast(oa, fcst, 20.0)] == [
        c.customer_id for c in visible_forecast(ob, fcst, 20.0)
    ]


def test_fulfillment_audit_smoke_on_few_rows():
    art = audit_frontier_unfulfilled(limit=2, iterations=20)
    assert art["n_audited"] == 2
    assert art["n_audited"] == 2
    for row in art["rows"]:
        assert "termination_reason" in row
