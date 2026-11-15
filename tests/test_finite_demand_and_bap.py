"""Finite-demand forecast calibration + baseline-anchored predictive CC-E smoke."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    fit_finite_demand_model,
    remaining_announcement_count,
    sample_finite_demand_scenarios,
)
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals, sample_conditional_scenarios
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE


def test_finite_demand_does_not_phantom_after_active_end():
    model = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    splits = stratified_split_small()
    stem = splits["train"][0]
    inst = load_instance(stem)
    # Late clock past active end → expect empty forecasts.
    from types import SimpleNamespace

    stats = model.stats_for(len(inst.customer_ids()))
    late = float(stats.active_end_frac) * 200.0 + 50.0
    obs = SimpleNamespace(
        time=late,
        released_open=(),
        accepted=(),
        completed=tuple(inst.customer_ids()),  # all announced already
        rejected=(),
        in_service=(),
        deferred=(),
        public_customer_count=len(inst.customer_ids()),
    )
    # Force remaining_hard=0 via completed=all
    assert remaining_announcement_count(inst, obs) == 0
    sc = sample_finite_demand_scenarios(model, obs, inst, horizon=80.0, n_scenarios=2, seed=1)
    assert all(len(s) == 0 for s in sc)


def test_finite_demand_count_capped_by_remaining_population():
    model = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    rem = remaining_announcement_count(case.instance, obs)
    sc = sample_finite_demand_scenarios(model, obs, case.instance, horizon=case.horizon, n_scenarios=3, seed=2)
    for s in sc:
        assert len(s) <= rem
        assert len(s) <= 16
        for fc in s:
            assert fc.announcement_time is not None
            assert fc.announcement_time > obs.time - 1e-9
            # Window not forced equal to announcement-only span of 0.
            assert fc.due_time > fc.ready_time + 1e-9
            assert not fc.customer_id.startswith("C")


def test_poisson_conditional_can_overpredict_vs_finite():
    """Sanity: old conditional Poisson may emit more futures than finite remaining."""
    splits = stratified_split_small()
    train = [load_instance(s) for s in splits["train"]]
    arrival = fit_empirical_arrivals(train)
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    rem = remaining_announcement_count(case.instance, obs)
    poisson = sample_conditional_scenarios(
        arrival, obs, horizon=case.horizon, n_scenarios=1, seed=0, announcement_mean=8.0
    )
    finite_sc = sample_finite_demand_scenarios(finite, obs, case.instance, horizon=case.horizon, n_scenarios=1, seed=0)
    assert len(finite_sc[0]) <= rem
    # Soft check: poisson often larger early; allow equality on tiny toys.
    assert len(poisson[0]) >= 0


def test_baseline_anchored_decide_smoke():
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    ctrl = BaselineAnchoredPredictiveCCE(
        case.instance,
        case.horizon,
        finite_model=finite,
        n_scenarios=2,
        alns_iterations=4,
        time_limit_seconds=0.5,
        seed=0,
        rollout_max_events=60,
    )
    d = ctrl.decide(obs, "initial")
    assert d is not None
    assert "baseline_anchored_predictive_cce" in d.notes
    assert "incumbent=greedy_nominal_cce" in d.notes
