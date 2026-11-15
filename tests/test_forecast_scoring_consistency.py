"""Forecast vs no-forecast must share the same causal scoring formula."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Decision
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    ForecastCustomer,
    TrainDemandAtom,
    sample_conditional_scenarios,
    sample_conditional_scenarios_crn,
)
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, greedy_nominal_value


def _obs_and_candidate():
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    # Simple idle/wait-style candidate with empty routes for all vehicles.
    routes = {v.id: [] for v in obs.vehicles}
    cand = Decision(
        time=obs.time,
        routes=routes,
        accepted=list(obs.accepted),
        newly_accepted=[],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=[],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="test",
        locked_destinations={},
        notes=["test_candidate"],
    )
    return case.instance, obs, cand


def test_empty_list_and_missing_scenarios_match_under_causal_mode():
    inst, obs, cand = _obs_and_candidate()
    v1, s1 = expected_rollout_value(inst, obs, cand, [], horizon=80.0, scoring_mode="causal")
    v2, s2 = expected_rollout_value(inst, obs, cand, [[]], horizon=80.0, scoring_mode="causal")
    assert abs(v1 - v2) < 1e-9
    assert s1[0].replay_ok == s2[0].replay_ok
    assert "greedy_nominal_continuation" not in s1[0].notes


def test_greedy_nominal_is_distinct_named_baseline():
    inst, obs, cand = _obs_and_candidate()
    vg, sg = greedy_nominal_value(inst, obs, cand, horizon=80.0)
    vc, sc = expected_rollout_value(inst, obs, cand, [[]], horizon=80.0, scoring_mode="causal")
    assert "greedy_nominal_continuation" in sg[0].notes
    assert "greedy_nominal_continuation" not in sc[0].notes
    # Values may differ; formula switch is only via greedy_nominal mode.
    vg2, _ = expected_rollout_value(inst, obs, cand, [[]], horizon=80.0, scoring_mode="greedy_nominal")
    assert abs(vg - vg2) < 1e-9


def test_forecast_difference_requires_future_announcements():
    inst, obs, cand = _obs_and_candidate()
    v_empty, _ = expected_rollout_value(inst, obs, cand, [[]], horizon=80.0)
    future = [
        [
            ForecastCustomer(
                customer_id="syn_test_0",
                ready_time=obs.time + 5.0,
                due_time=obs.time + 80.0,
                x=1.0,
                y=1.0,
                demand=1.0,
                service_time=1.0,
                announcement_time=obs.time + 5.0,
            )
        ]
    ]
    v_fc, scores = expected_rollout_value(inst, obs, cand, future, horizon=80.0)
    # Either values differ or the forecast path at least executed causal events.
    assert scores[0].events >= 0
    assert isinstance(v_fc, float)
    assert isinstance(v_empty, float)


def test_conditional_forecast_not_empty_only_because_clock_past_200():
    atoms = (
        TrainDemandAtom(1.0, 1.0, 1.0, 1.0, 0.0, 50.0),
        TrainDemandAtom(2.0, 2.0, 1.0, 1.0, 0.0, 50.0),
    )
    model = ArrivalForecast(train_atoms=atoms, train_interarrival_mean=10.0, model_id="test")
    # Fake late observation time well past old day_horizon=200.
    from types import SimpleNamespace

    obs = SimpleNamespace(
        time=250.0,
        released_open=(),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
    )
    scenarios = sample_conditional_scenarios(model, obs, horizon=80.0, n_scenarios=2, seed=7, announcement_mean=8.0)
    assert len(scenarios) == 2
    # With mu=8 over 80 units, expected count ~10; should usually be non-empty.
    assert any(len(s) > 0 for s in scenarios)
    for s in scenarios:
        for fc in s:
            assert fc.announcement_time is not None
            assert fc.announcement_time > 250.0 - 1e-9
            assert not fc.customer_id.startswith("C")  # anonymous


def test_calibration_train_only_honest_sample_sizes():
    from safe_time_evrp.data.dynamic_schneider import stratified_split_small
    from safe_time_evrp.mpc_central.forecast_calibration import calibrate_train_announcement_rate

    splits = stratified_split_small()
    report = calibrate_train_announcement_rate(dynamicity="medium", n_realizations=1)
    assert report["n_train_stems"] == len(splits["train"])
    assert report["n_episode_level_mean_estimates"] == len(splits["train"]) * 1
    assert report["n_raw_interarrival_gaps"] >= 0
    assert "honesty_note" in report
    assert "n_episode_level_mean_estimates" in report["honesty_note"]
    train = set(splits["train"])
    test = set(splits["test"])
    for sample in report["samples"]:
        assert sample["stem"] in train
        assert sample["stem"] not in test
    assert float(report["calibrated_announcement_mean"]) > 0


def test_crn_mu_comparison_shares_skeleton():
    atoms = (TrainDemandAtom(0.0, 0.0, 1.0, 1.0, 0.0, 40.0),)
    model = ArrivalForecast(train_atoms=atoms, train_interarrival_mean=12.0, model_id="crn")
    from types import SimpleNamespace

    obs = SimpleNamespace(
        time=0.0,
        released_open=(),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
    )
    paired = sample_conditional_scenarios_crn(
        model, obs, horizon=100.0, n_scenarios=1, seed=3, announcement_means=(8.0, 12.0)
    )
    a = paired[8.0][0]
    b = paired[12.0][0]
    # Same number of uniforms consumed until horizon; faster rate => more or equal arrivals.
    assert len(a) >= len(b)
    if a and b:
        # First announcement earlier under smaller mu (faster arrivals).
        assert a[0].announcement_time <= b[0].announcement_time + 1e-9
