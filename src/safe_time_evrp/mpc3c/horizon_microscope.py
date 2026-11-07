"""Tiny instance where increasing H changes the present first action."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, ForecastCustomer
from safe_time_evrp.testbed.constructor import make_observation


def horizon_fork_instance():
    """Myopic/short-H serves A first; long-H with B forecast reorders to B first.

    A is released at t=0. B is only a forecast with ready=5. Under constructive
    insertion, planning A alone yields first action A; planning A+B yields B
    first (cheapest joint tour). Short H defers B; long H includes the forecast.
    """
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
        Node("B", NodeKind.CUSTOMER, 0, 8, 1, TimeWindow(5, 100), 1),
        Node("S", NodeKind.CHARGER, 0, 4, 0, TimeWindow(0, 200), 0),
    ]
    vehicle = VehicleType(
        battery_capacity=20.0,
        load_capacity=10.0,
        consumption_rate=1.0,
        inverse_recharge_rate=0.2,
        velocity=1.0,
        recharge_policy="full",
    )
    return build_euclidean_instance(
        "horizon_fork",
        nodes,
        vehicle,
        source_format="gate3d_toy",
        source_name="horizon_causality_microscope",
        assumptions=("euclidean_toy_for_horizon_H_causality",),
    )


def _obs_only_a(instance, fleet_size: int = 1) -> Observation:
    base = make_observation(instance, fleet_size, start_time=0.0)
    return Observation(
        base.time,
        base.vehicles,
        ("A",),
        (),
        (),
        (),
        (),
        (),
    )


def foresight_scenarios() -> ArrivalForecast:
    return ArrivalForecast(
        scenarios=[[ForecastCustomer("B", ready_time=5.0, due_time=100.0, source="microscope")]],
        train_interarrival_mean=5.0,
        train_customer_pool=("A", "B"),
    )


def present_action_for_horizon(horizon: float, *, use_forecast: bool = True) -> tuple[str | None, str | None]:
    instance = horizon_fork_instance()
    obs = _obs_only_a(instance)
    forecasts = foresight_scenarios().sample_within(0.0, horizon) if use_forecast else []
    decision = decide(
        instance,
        obs,
        ControllerKind.RH_OPEN_LOOP,
        horizon=horizon,
        forecast_customers=forecasts,
    )
    first = decision.first_actions[obs.vehicles[0].id]
    if first is None:
        return None, None
    return first.node_id, first.purpose


def search_horizon_causality() -> dict:
    """Honest search: report whether any H pair changes the present action."""
    short = present_action_for_horizon(1.0, use_forecast=True)
    long = present_action_for_horizon(20.0, use_forecast=True)
    myopic = present_action_for_horizon(20.0, use_forecast=False)
    grid = {h: present_action_for_horizon(float(h), use_forecast=True) for h in (0.5, 1.0, 3.0, 6.0, 10.0, 20.0)}
    return {
        "instance": "horizon_fork",
        "short_H": 1.0,
        "long_H": 20.0,
        "action_short": short,
        "action_long": long,
        "action_no_forecast": myopic,
        "horizon_changes_present_action": short != long,
        "grid": {str(k): v for k, v in grid.items()},
        "mechanism": (
            "Short H excludes forecast B (ready=5); long H includes B in planning observation; "
            "constructive insertion then changes the present first customer from A to B."
        ),
    }
