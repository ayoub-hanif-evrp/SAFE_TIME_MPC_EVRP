"""Stage 1 validity: matched incumbent, info boundary, honest calibration hooks."""

from __future__ import annotations

from dataclasses import replace

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import TimeWindow
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    calibration_report_finite_vs_poisson,
    fit_finite_demand_model,
    remaining_announcement_count,
    sample_finite_demand_scenarios,
)
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey


def _prep_case():
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    return case, sim.observation()


def test_observation_exposes_public_customer_count():
    case, obs = _prep_case()
    assert obs.public_customer_count == len(case.instance.customer_ids())
    rem = remaining_announcement_count(case.instance, obs)
    assert rem == obs.public_customer_count - len(
        set(obs.released_open)
        | set(obs.accepted)
        | set(obs.completed)
        | set(obs.rejected)
        | set(obs.in_service)
        | set(obs.deferred)
    )


def test_zero_override_matches_standalone_greedy_first_action():
    case, obs = _prep_case()
    common = dict(
        alns_iterations=6,
        time_limit_seconds=0.4,
        seed=7,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=80,
    )
    bap = BaselineAnchoredPredictiveCCE(
        case.instance,
        case.horizon,
        allow_override=False,
        use_finite_demand=False,
        equivalence_mode=True,
        **common,
    )
    gn_eq = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        use_forecast=False,
        use_persistent_certificate=True,
        scoring_mode="greedy_nominal",
        alns_iterations=common["alns_iterations"],
        time_limit_seconds=1e9,
        seed=common["seed"],
        max_replan_interval=common["max_replan_interval"],
        rollout_max_events=common["rollout_max_events"],
    )
    assert bap.store is bap._incumbent.store
    assert bap._incumbent.time_limit_seconds == gn_eq.time_limit_seconds
    d0 = gn_eq.decide(obs, "initial")
    d1 = bap.decide(obs, "initial")
    assert FirstActionKey.from_decision(d0) == FirstActionKey.from_decision(d1)
    assert "zero_override_passthrough" in d1.notes
    assert "matched_incumbent_budget=1" in d1.notes
    assert "equivalence_mode=1" in d1.notes


def test_hidden_future_attributes_do_not_change_online_decision():
    """Mutate unreleased customer coords/windows; public observation unchanged → same decide."""
    case, obs = _prep_case()
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    announced = (
        set(obs.released_open)
        | set(obs.accepted)
        | set(obs.completed)
        | set(obs.rejected)
        | set(obs.in_service)
        | set(obs.deferred)
    )
    inst_a = case.instance
    # Clone graph with mutated unreleased customers.
    nodes = dict(inst_a.nodes)
    for cid in inst_a.customer_ids():
        if cid in announced:
            continue
        n = nodes[cid]
        nodes[cid] = replace(
            n,
            x=n.x + 50.0,
            y=n.y - 50.0,
            demand=n.demand * 2.0,
            window=TimeWindow(n.window.ready + 10.0, n.window.due + 10.0),
        )
    inst_b = replace(inst_a, name=inst_a.name + "_mut", nodes=nodes)
    # Same public observation object (includes public_customer_count).
    ctrl_a = BaselineAnchoredPredictiveCCE(
        inst_a,
        case.horizon,
        finite_model=finite,
        allow_override=True,
        alns_iterations=4,
        time_limit_seconds=0.35,
        seed=3,
        rollout_max_events=40,
    )
    ctrl_b = BaselineAnchoredPredictiveCCE(
        inst_b,
        case.horizon,
        finite_model=finite,
        allow_override=True,
        alns_iterations=4,
        time_limit_seconds=0.35,
        seed=3,
        rollout_max_events=40,
    )
    # Forecast sampling must not depend on mutated hidden attrs when using same obs + public N.
    sc_a = sample_finite_demand_scenarios(finite, obs, inst_a, horizon=case.horizon, n_scenarios=1, seed=3)
    sc_b = sample_finite_demand_scenarios(finite, obs, inst_b, horizon=case.horizon, n_scenarios=1, seed=3)
    assert len(sc_a[0]) == len(sc_b[0])
    for fa, fb in zip(sc_a[0], sc_b[0], strict=True):
        assert fa.customer_id == fb.customer_id
        assert abs(fa.x - fb.x) < 1e-9
        assert abs(fa.announcement_time - fb.announcement_time) < 1e-9
    da = ctrl_a.decide(obs, "initial")
    db = ctrl_b.decide(obs, "initial")
    assert FirstActionKey.from_decision(da) == FirstActionKey.from_decision(db)


def test_calibration_report_includes_honest_segment_metrics():
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    report = calibration_report_finite_vs_poisson(finite=finite, poisson_mu=6.12, n_realizations=1)
    assert "honesty_note" in report
    assert report["mean_abs_segment_error_finite"] is not None
    assert report["mean_abs_segment_error_poisson"] is not None
    assert report["poisson_over_realized_ratio"] > report["finite_over_realized_ratio"]
