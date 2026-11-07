"""Matched Gate 3C/3D controllers with a real planning horizon."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Anchor, Observation, Visit
from safe_time_evrp.mpc3c.flexibility import flexibility_terminal_value
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, information_safe_remaining
from safe_time_evrp.optimization.insertion import construct_routes
from safe_time_evrp.testbed.constructor import make_observation


class ControllerKind(str, Enum):
    MYOPIC = "myopic"
    RH_OPEN_LOOP = "rh_open_loop"
    ROLLOUT = "rollout"
    FLEXIBILITY = "flexibility_mpc"


@dataclass
class ControllerDecision:
    kind: str
    routes: dict[str, list[Visit]]
    first_actions: dict[str, Visit | None]
    score: float
    notes: list[str] = field(default_factory=list)


def _anchors_after_plan(
    instance: Instance, observation: Observation, routes: dict[str, list[Visit]]
) -> dict[str, Anchor]:
    model = NominalLinearEnergy()
    out: dict[str, Anchor] = {}
    for vehicle in observation.vehicles:
        result = evaluate_route(instance, vehicle.anchor, routes.get(vehicle.id, []), model)
        if result.feasible:
            out[vehicle.id] = Anchor(result.end_node, result.end_time, result.end_soc, result.end_load, frozenset())
        else:
            out[vehicle.id] = vehicle.anchor
    return out


def _plan_score_distance(plan_distance: float, charge_time: float) -> float:
    return -(plan_distance + 0.1 * charge_time)


def _with_forecasts(observation: Observation, forecast_customers: list[ForecastCustomer]) -> Observation:
    """Planning observation: released open plus forecast IDs inside the horizon."""
    if not forecast_customers:
        return observation
    extra = [f.customer_id for f in forecast_customers if f.customer_id not in observation.released_open]
    if not extra:
        return observation
    return Observation(
        observation.time,
        observation.vehicles,
        tuple(list(observation.released_open) + extra),
        observation.accepted,
        observation.completed,
        observation.rejected,
        observation.in_service,
        observation.deferred,
    )


def decide(
    instance: Instance,
    observation: Observation,
    kind: ControllerKind,
    *,
    horizon: float,
    compute_budget_variants: int = 8,
    forecast_customers: list[ForecastCustomer] | None = None,
) -> ControllerDecision:
    """Choose fleet suffixes; ``horizon`` is used by all Gate 3C/3D controllers.

    ``forecast_customers`` are anticipatory demand samples visible only as forecasts.
    They may enter planning observations but must not be treated as plant-released
    commitments by the experiment harness.
    """
    model = NominalLinearEnergy()
    forecasts = list(forecast_customers or [])
    if kind is ControllerKind.MYOPIC:
        # Myopic: only customers already ready; ignore forecasts and later releases.
        ready_ids = [
            cid for cid in observation.released_open if instance.node(cid).window.ready <= observation.time + 1e-9
        ]
        obs = Observation(
            observation.time,
            observation.vehicles,
            tuple(ready_ids),
            observation.accepted,
            observation.completed,
            observation.rejected,
            observation.in_service,
            observation.deferred,
        )
        plan = construct_routes(instance, obs, horizon=0.0, energy=model)
        score = _plan_score_distance(plan.total_distance, plan.total_charge_time)
        return _pack(
            kind,
            plan.routes,
            observation,
            score,
            [f"horizon_used={horizon}", "myopic_ready_only", f"forecasts_ignored={len(forecasts)}"],
        )

    plan_obs = _with_forecasts(observation, forecasts)

    if kind is ControllerKind.RH_OPEN_LOOP:
        plan = construct_routes(instance, plan_obs, horizon=horizon, energy=model)
        score = _plan_score_distance(plan.total_distance, plan.total_charge_time)
        return _pack(
            kind,
            plan.routes,
            observation,
            score,
            [f"horizon_used={horizon}", f"forecast_count={len(forecasts)}"],
        )

    if kind is ControllerKind.ROLLOUT:
        base = construct_routes(instance, plan_obs, horizon=horizon, energy=model)
        best_routes = base.routes
        best_score = _plan_score_distance(base.total_distance, base.total_charge_time)
        notes = [f"horizon_used={horizon}", "rollout=perfect_information_prefix", f"forecast_count={len(forecasts)}"]
        optionals = list(plan_obs.released_open)[:compute_budget_variants]
        for cid in optionals:
            obs = Observation(
                plan_obs.time,
                plan_obs.vehicles,
                plan_obs.released_open,
                tuple(sorted(set(plan_obs.accepted) | {cid})),
                plan_obs.completed,
                plan_obs.rejected,
                plan_obs.in_service,
                plan_obs.deferred,
            )
            plan = construct_routes(instance, obs, horizon=horizon, energy=model)
            if not plan.feasible_commitments:
                continue
            score = _plan_score_distance(plan.total_distance, plan.total_charge_time)
            if score > best_score:
                best_score = score
                best_routes = plan.routes
        return _pack(kind, best_routes, observation, best_score, notes)

    if kind is ControllerKind.FLEXIBILITY:
        lam = 0.75
        candidates: list[tuple[float, dict[str, list[Visit]], list[str]]] = []
        base = construct_routes(instance, plan_obs, horizon=horizon, energy=model)
        candidates.append((_plan_score_distance(base.total_distance, base.total_charge_time), base.routes, ["base"]))
        optionals = list(plan_obs.released_open)[:compute_budget_variants]
        for cid in optionals:
            obs = Observation(
                plan_obs.time,
                plan_obs.vehicles,
                plan_obs.released_open,
                tuple(sorted(set(plan_obs.accepted) | {cid})),
                plan_obs.completed,
                plan_obs.rejected,
                plan_obs.in_service,
                plan_obs.deferred,
            )
            plan = construct_routes(instance, obs, horizon=horizon, energy=model)
            if plan.feasible_commitments:
                candidates.append(
                    (
                        _plan_score_distance(plan.total_distance, plan.total_charge_time),
                        plan.routes,
                        [f"prefix:{cid}"],
                    )
                )
        best_score = float("-inf")
        best_routes = base.routes
        best_notes = [f"horizon_used={horizon}", f"lambda={lam}", f"forecast_count={len(forecasts)}"]
        for dist_score, routes, note in candidates:
            anchors = _anchors_after_plan(instance, observation, routes)
            rem = information_safe_remaining(observation, forecasts, routes)
            flex = 0.0
            for vehicle in observation.vehicles:
                flex += flexibility_terminal_value(instance, anchors[vehicle.id], rem)
            total = dist_score + lam * flex
            if total > best_score:
                best_score = total
                best_routes = routes
                best_notes = [
                    f"horizon_used={horizon}",
                    f"lambda={lam}",
                    f"flex={flex:.3f}",
                    f"forecast_count={len(forecasts)}",
                    *note,
                ]
        return _pack(kind, best_routes, observation, best_score, best_notes)

    raise ValueError(kind)


def _pack(
    kind: ControllerKind,
    routes: dict[str, list[Visit]],
    observation: Observation,
    score: float,
    notes: list[str],
) -> ControllerDecision:
    first: dict[str, Visit | None] = {}
    for vehicle in observation.vehicles:
        visits = routes.get(vehicle.id, [])
        first[vehicle.id] = visits[0] if visits else None
    return ControllerDecision(kind.value, routes, first, score, notes)


def static_all_released_observation(instance: Instance, fleet_size: int) -> Observation:
    return make_observation(instance, fleet_size, start_time=0.0)
