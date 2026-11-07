"""Executable horizon causality: longer H changes a legal physical first action.

Gate 3E: claims use the post-strip, revalidated dispatch — never an unreleased
forecast service that the harness would discard before execution.
"""

from __future__ import annotations

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, ForecastCustomer, augment_instance_for_planning
from safe_time_evrp.mpc3c.sim_experiment import _clean_and_revalidate
from safe_time_evrp.testbed.constructor import make_observation


def horizon_fork_instance():
    """Short H serves A; long H with anonymous forecast yields proactive charge first."""
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
        Node("S", NodeKind.CHARGER, 0, 2, 0, TimeWindow(0, 200), 0),
    ]
    vehicle = VehicleType(
        battery_capacity=11.0,
        load_capacity=10.0,
        consumption_rate=1.0,
        inverse_recharge_rate=0.15,
        velocity=1.0,
        recharge_policy="full",
    )
    return build_euclidean_instance(
        "horizon_fork_executable",
        nodes,
        vehicle,
        source_format="gate3e_toy",
        source_name="executable_horizon_causality_microscope",
        assumptions=("euclidean_toy_executable_H_causality",),
    )


def _obs_only_a(instance, fleet_size: int = 1) -> Observation:
    base = make_observation(instance, fleet_size, start_time=0.0)
    return Observation(base.time, base.vehicles, ("A",), (), (), (), (), ())


def foresight_scenarios() -> ArrivalForecast:
    return ArrivalForecast(
        scenarios=[
            [
                ForecastCustomer(
                    "syn_far_0",
                    ready_time=5.0,
                    due_time=60.0,
                    x=0.0,
                    y=3.5,
                    demand=1.0,
                    service_time=1.0,
                    source="microscope_anonymous",
                )
            ]
        ],
        train_interarrival_mean=5.0,
        model_id="microscope",
    )


def executed_action_for_horizon(horizon: float, *, use_forecast: bool = True) -> tuple[str | None, str | None]:
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
    cleaned = _clean_and_revalidate(instance, obs, decision.routes)
    model = NominalLinearEnergy()
    vid = obs.vehicles[0].id
    visits = cleaned.get(vid, [])
    if visits:
        result = evaluate_route(instance, obs.vehicles[0].anchor, visits, model)
        assert result.feasible, result.reason
    if not visits:
        return None, None
    first = visits[0]
    assert not (first.purpose == "service" and str(first.node_id).startswith("syn_"))
    return first.node_id, first.purpose


def planned_action_for_horizon(horizon: float, *, use_forecast: bool = True) -> tuple[str | None, str | None]:
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
    short_exec = executed_action_for_horizon(1.0, use_forecast=True)
    long_exec = executed_action_for_horizon(20.0, use_forecast=True)
    no_fcst = executed_action_for_horizon(20.0, use_forecast=False)
    grid = {h: executed_action_for_horizon(float(h), use_forecast=True) for h in (0.5, 1.0, 3.0, 6.0, 10.0, 20.0)}
    plant = horizon_fork_instance()
    fc = foresight_scenarios().scenarios[0]
    aug = augment_instance_for_planning(plant, fc)
    assert "syn_far_0" in aug.customer_ids() and "syn_far_0" not in plant.customer_ids()
    return {
        "instance": "horizon_fork_executable",
        "short_H": 1.0,
        "long_H": 20.0,
        "executed_action_short": short_exec,
        "executed_action_long": long_exec,
        "executed_action_no_forecast": no_fcst,
        "planned_action_short": planned_action_for_horizon(1.0),
        "planned_action_long": planned_action_for_horizon(20.0),
        "horizon_changes_executed_action": short_exec != long_exec,
        # Gate 3D field kept for older readers; means executed action under 3E.
        "horizon_changes_present_action": short_exec != long_exec,
        "action_short": short_exec,
        "action_long": long_exec,
        "action_no_forecast": no_fcst,
        "grid": {str(k): v for k, v in grid.items()},
        "grid_executed": {str(k): v for k, v in grid.items()},
        "mechanism": (
            "Long H includes anonymous forecast demand; constructive plan may visit the "
            "synthetic stop, but after strip+revalidate the dispatched first action is a "
            "legal proactive charge at S. Short H dispatches A service. Claim is on executed actions."
        ),
    }


def present_action_for_horizon(horizon: float, *, use_forecast: bool = True) -> tuple[str | None, str | None]:
    return executed_action_for_horizon(horizon, use_forecast=use_forecast)
