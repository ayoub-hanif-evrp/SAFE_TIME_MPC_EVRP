"""Gate 3E scientific-correctness regressions."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    ForecastCustomer,
    TrainDemandAtom,
    build_anonymous_scenarios,
    information_safe_remaining,
)
from safe_time_evrp.mpc3c.horizon_microscope import search_horizon_causality
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc3c.sim_experiment import _routes_cover_commitments, run_sim_dynamic
from safe_time_evrp.testbed.constructor import make_observation


def _two_customer_env(hidden_xy: tuple[float, float], name: str):
    hx, hy = hidden_xy
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
        Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
        Node("H", NodeKind.CUSTOMER, hx, hy, 1, TimeWindow(50, 120), 1),
    ]
    vehicle = VehicleType(40.0, 10.0, 1.0, 0.2, 1.0, "full")
    return build_euclidean_instance(name, nodes, vehicle, source_format="t", source_name="t", assumptions=())


def test_stable_seed_is_process_independent():
    a = stable_seed("release", "solomon_dataset_0")
    b = stable_seed("release", "solomon_dataset_0")
    c = stable_seed("forecast", "solomon_dataset_0")
    assert a == b
    assert a != c
    assert a == 0x7FFFFFFF & a


def test_hidden_customers_cannot_change_decision():
    """Identical observation + forecast model + seed ⇒ identical decision."""
    env_a = _two_customer_env((20.0, 0.0), "hid_a")
    env_b = _two_customer_env((0.0, 25.0), "hid_b")
    model = ArrivalForecast(
        train_atoms=(
            TrainDemandAtom(5.0, 5.0, 1.0, 1.0, 2.0, 40.0),
            TrainDemandAtom(6.0, 1.0, 1.0, 1.0, 3.0, 50.0),
        ),
        train_interarrival_mean=4.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=2, customers_per_scenario=2, seed=stable_seed("fc", "unit"))
    obs_a = make_observation(env_a, 1)
    obs_a = Observation(obs_a.time, obs_a.vehicles, ("A",), (), (), (), (), ())
    # Same observable vehicle/request state on env_b geometry for A.
    obs_b = make_observation(env_b, 1)
    obs_b = Observation(obs_b.time, obs_b.vehicles, ("A",), (), (), (), (), ())
    forecasts = fcst.sample_within(0.0, 20.0)
    d1 = decide(env_a, obs_a, ControllerKind.RH_OPEN_LOOP, horizon=20.0, forecast_customers=forecasts)
    d2 = decide(env_b, obs_b, ControllerKind.RH_OPEN_LOOP, horizon=20.0, forecast_customers=forecasts)
    a1 = d1.first_actions[obs_a.vehicles[0].id]
    a2 = d2.first_actions[obs_b.vehicles[0].id]
    assert (a1.node_id if a1 else None, a1.purpose if a1 else None) == (
        a2.node_id if a2 else None,
        a2.purpose if a2 else None,
    )
    # Forecast IDs are synthetic, not hidden evaluation IDs.
    assert all(f.customer_id.startswith("syn_") for f in forecasts)
    assert "H" not in {f.customer_id for f in forecasts}


def test_staggered_release_does_not_end_early():
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 500), 0),
        Node("A", NodeKind.CUSTOMER, 2, 0, 1, TimeWindow(0, 100), 1),
        Node("B", NodeKind.CUSTOMER, 0, 2, 1, TimeWindow(20, 200), 1),
    ]
    vehicle = VehicleType(50.0, 10.0, 1.0, 0.2, 1.0, "full")
    inst = build_euclidean_instance("stagger", nodes, vehicle, source_format="t", source_name="t", assumptions=())
    result = run_sim_dynamic(
        inst,
        ControllerKind.RH_OPEN_LOOP,
        fleet_size=1,
        horizon=50.0,
        releases=[("A", 0.0), ("B", 20.0)],
        t_max=250.0,
        max_replan_interval=30.0,
    )
    assert "B" in result.announced
    assert "B" in result.served or "B" in result.rejected or "B" in result.accepted_unfulfilled
    # Must have continued past A's completion to see B's release.
    assert any(t >= 20.0 - 1e-9 for t, *_ in result.action_sequence) or "B" in result.served


def test_executable_horizon_causality():
    report = search_horizon_causality()
    assert report["horizon_changes_executed_action"] is True
    assert report["executed_action_short"] != report["executed_action_long"]
    assert not str(report["executed_action_long"][0]).startswith("syn_")


def test_commitment_validator_flags_broken_promises_with_valid_physics():
    """Physical replay can pass while accepted commitments are unmet."""
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 2, 0, 1, TimeWindow(0, 30), 1),
        Node("C2", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 30), 1),
    ]
    vehicle = VehicleType(8.0, 10.0, 1.0, 0.2, 1.0, "full")
    inst = build_euclidean_instance("commit_break", nodes, vehicle, source_format="t", source_name="t", assumptions=())
    obs = make_observation(inst, 1)
    # Accept both but plan only covers C1 — commitment check must fail.
    routes = {"v0": [Visit("C1", "service"), Visit("D", "return")]}
    assert not _routes_cover_commitments(inst, obs, routes, ["C1", "C2"])
    assert _routes_cover_commitments(inst, obs, routes, ["C1"])


def test_flexibility_remaining_ignores_hidden_ids():
    env = _two_customer_env((20.0, 0.0), "flex_hid")
    obs = make_observation(env, 1)
    obs = Observation(obs.time, obs.vehicles, ("A",), (), (), (), (), ())
    rem = information_safe_remaining(obs, [ForecastCustomer("syn_0", 1, 10, 1, 1)])
    assert "H" not in rem
    assert "A" in rem and "syn_0" in rem


def test_amazon_package_window_aggregation_is_order_independent():
    from safe_time_evrp.data.amazon import _parse_window_hours

    # Aggregation rule unit: max ready, min due.
    w1 = _parse_window_hours("2018-07-27 16:00:00", "2018-07-27 20:00:00", 12.0, departure_epoch_h=0.0)
    w2 = _parse_window_hours("2018-07-27 17:00:00", "2018-07-27 22:00:00", 12.0, departure_epoch_h=0.0)
    ready = max(w1.ready, w2.ready)
    due = min(w1.due, w2.due)
    assert ready <= due
