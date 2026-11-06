"""Nominal references used beside the certified controller.

B0 inserts one newly released customer if the nominal route evaluator accepts it,
then keeps dispatching the stored suffix when the vehicle becomes idle.
B1 is the Part 1 receding-horizon insertion controller. Neither uses the rectangle.
"""

from __future__ import annotations

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision
from safe_time_evrp.optimization.insertion import _variants
from safe_time_evrp.robust.backup import dispatch_suffix

_CONTINUE = {"arrive", "service_end", "charge_end", "wait_end"}


def run_nominal_mpc(instance: Instance, releases: list[tuple[str, float]], **kwargs):
    return run_episode(instance, releases, **kwargs)


def run_reactive(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
    t_max: float,
) -> dict[str, str]:
    """Accept a request only when one nominal insertion is feasible now."""
    simulator = FleetSimulator(instance, fleet_size)
    for customer_id, release_time in releases:
        simulator.schedule_release(customer_id, release_time)
    routes = {f"v{i + 1}": [] for i in range(fleet_size)}
    while True:
        nxt = simulator.next_event_time()
        if nxt is None or nxt > t_max + EPS:
            break
        event = simulator.pop_event()
        if event is None:
            break
        if event.kind == "request_release":
            _try_insert(instance, simulator, routes, event.payload["customer_id"])
        elif event.kind in _CONTINUE:
            _dispatch(instance, simulator, routes, event.kind)
    simulator.mark_finished()
    return {cid: status.value for cid, status in simulator.requests.items()}


def _try_insert(instance: Instance, simulator: FleetSimulator, routes: dict, customer_id: str) -> None:
    placed = False
    observation = simulator.observation()
    for vehicle in observation.vehicles:
        base = dispatch_suffix(
            routes[vehicle.id],
            observation,
            vehicle.anchor.node,
            vehicle.anchor.soc,
            instance.vehicle_type.battery_capacity,
        )
        for pos in range(len(base) + 1):
            options = _variants(base, pos, customer_id, instance.charger_ids(), instance.depot_id)
            for candidate in options:
                result = evaluate_route(instance, vehicle.anchor, candidate)
                if result.feasible and customer_id in result.served:
                    routes[vehicle.id] = result.visits[:-1]
                    placed = True
                    break
            if placed:
                break
        if placed:
            break
    if not placed:
        _dispatch(instance, simulator, routes, "request_release", reject=[customer_id])
        return
    _dispatch(instance, simulator, routes, "request_release", newly=[customer_id])


def _dispatch(
    instance: Instance,
    simulator: FleetSimulator,
    routes: dict,
    trigger: str,
    *,
    newly: list[str] | None = None,
    reject: list[str] | None = None,
) -> None:
    observation = simulator.observation()
    aligned = {}
    for vehicle in observation.vehicles:
        aligned[vehicle.id] = dispatch_suffix(
            routes.get(vehicle.id, []),
            observation,
            vehicle.anchor.node,
            vehicle.anchor.soc,
            instance.vehicle_type.battery_capacity,
        )
        routes[vehicle.id] = list(aligned[vehicle.id])
    decision = Decision(
        time=simulator.time,
        routes=aligned,
        accepted=list(observation.accepted) + list(newly or []),
        newly_accepted=list(newly or []),
        rejected=list(reject or []),
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=[
            visit.node_id for visits in aligned.values() for visit in visits if visit.purpose == "service"
        ],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger=trigger,
        locked_destinations={vehicle.id: vehicle.locked_destination for vehicle in observation.vehicles},
    )
    simulator.apply_decision(decision)


def nominal_controller(instance: Instance, horizon: float) -> EventTriggeredMPC:
    return EventTriggeredMPC(instance, horizon)
