"""Deterministic cheapest insertion with explicit feasibility checks.

This is a constructive baseline, not an exact solver and not a feasibility certificate.
Mandatory accepted customers are inserted before any new acceptance. A customer whose
window opens after the planning horizon is deferred rather than rejected, unless that
customer is already an accepted commitment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation, Visit


@dataclass
class InsertionPlan:
    routes: dict[str, list[Visit]]
    accepted: list[str]
    newly_accepted: list[str]
    rejected: list[str]
    deferred: list[str]
    planned_service: list[str]
    total_distance: float
    total_charge_time: float
    horizon_extended: bool
    feasible_commitments: bool
    notes: list[str] = field(default_factory=list)


def _variants(
    route: list[Visit],
    pos: int,
    customer_id: str,
    stations: list[str],
    depot_id: str,
) -> list[list[Visit]]:
    service = Visit(customer_id, "service")
    built: list[list[Visit]] = []
    direct = route[:pos] + [service] + route[pos:]
    built.append(direct)
    reload = route[:pos] + [Visit(depot_id, "reload"), service] + route[pos:]
    built.append(reload)
    for station in stations:
        charge = Visit(station, "charge")
        built.append(route[:pos] + [charge, service] + route[pos:])
        built.append(route[:pos] + [service, charge] + route[pos:])
        built.append(route[:pos] + [Visit(depot_id, "reload"), charge, service] + route[pos:])
    return built


def _place(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    customer_id: str,
    owner: str | None,
    energy: NominalLinearEnergy,
) -> bool:
    stations = instance.charger_ids()
    best_key: tuple[float, float, str, int] | None = None
    best: tuple[str, list[Visit]] | None = None
    vehicles = observation.vehicles if owner is None else tuple(v for v in observation.vehicles if v.id == owner)
    for vehicle in vehicles:
        route = routes[vehicle.id]
        for pos in range(len(route) + 1):
            for candidate in _variants(route, pos, customer_id, stations, instance.depot_id):
                result = evaluate_route(instance, vehicle.anchor, candidate, energy)
                if not result.feasible or customer_id not in result.served:
                    continue
                key = (result.distance, result.charge_time, vehicle.id, pos)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (vehicle.id, result.visits[:-1])  # drop the appended return
    if best is None:
        return False
    routes[best[0]] = best[1]
    return True


def construct_routes(
    instance: Instance,
    observation: Observation,
    *,
    horizon: float,
    energy: NominalLinearEnergy | None = None,
) -> InsertionPlan:
    model = energy or NominalLinearEnergy()
    now = observation.time
    in_service = set(observation.in_service)
    completed = set(observation.completed)
    rejected = set(observation.rejected)
    accepted = [c for c in observation.accepted if c not in completed and c not in in_service]
    owner: dict[str, str] = {}
    for vehicle in observation.vehicles:
        for customer_id in vehicle.anchor.onboard:
            owner[customer_id] = vehicle.id
        if vehicle.locked_destination in instance.nodes:
            node = instance.node(vehicle.locked_destination)
            if node.kind.value == "customer" and vehicle.locked_destination in accepted:
                owner.setdefault(vehicle.locked_destination, vehicle.id)

    deferred: list[str] = []
    optional: list[str] = []
    open_ids = [
        cid
        for cid in observation.released_open
        if cid not in completed and cid not in rejected and cid not in in_service
    ]
    for customer_id in open_ids:
        if customer_id in accepted:
            continue
        ready = instance.node(customer_id).window.ready
        if ready > now + horizon:
            deferred.append(customer_id)
        else:
            optional.append(customer_id)

    horizon_extended = any(instance.node(cid).window.ready > now + horizon for cid in accepted)
    routes: dict[str, list[Visit]] = {vehicle.id: [] for vehicle in observation.vehicles}
    notes: list[str] = []
    mandatory_ok = True
    for customer_id in sorted(accepted, key=lambda cid: (instance.node(cid).window.due, cid)):
        if not _place(instance, observation, routes, customer_id, owner.get(customer_id), model):
            mandatory_ok = False
            notes.append(f"no_insertion_for_commitment:{customer_id}")

    newly_accepted: list[str] = []
    newly_rejected: list[str] = []
    if mandatory_ok:
        for customer_id in sorted(optional, key=lambda cid: (instance.node(cid).window.due, cid)):
            pinned = owner.get(customer_id)
            if _place(
                instance,
                observation,
                routes,
                customer_id,
                pinned,
                model,
            ):
                newly_accepted.append(customer_id)
            else:
                newly_rejected.append(customer_id)
    else:
        notes.append("optional_customers_not_considered_because_commitments_failed")

    planned: list[str] = []
    distance = 0.0
    charge_time = 0.0
    if mandatory_ok:
        finalized: dict[str, list[Visit]] = {}
        for vehicle in observation.vehicles:
            result = evaluate_route(instance, vehicle.anchor, routes[vehicle.id], model)
            if not result.feasible:
                mandatory_ok = False
                notes.append(f"route_became_infeasible:{vehicle.id}:{result.reason}")
                break
            finalized[vehicle.id] = result.visits
            planned.extend(result.served)
            distance += result.distance
            charge_time += result.charge_time
        if mandatory_ok:
            routes = finalized

    accepted_out = list(observation.accepted)
    for customer_id in newly_accepted:
        if customer_id not in accepted_out:
            accepted_out.append(customer_id)

    return InsertionPlan(
        routes=routes if mandatory_ok else {vehicle.id: [] for vehicle in observation.vehicles},
        accepted=accepted_out,
        newly_accepted=newly_accepted if mandatory_ok else [],
        rejected=newly_rejected if mandatory_ok else [],
        deferred=sorted(deferred),
        planned_service=sorted(planned) if mandatory_ok else [],
        total_distance=distance if mandatory_ok else 0.0,
        total_charge_time=charge_time if mandatory_ok else 0.0,
        horizon_extended=horizon_extended,
        feasible_commitments=mandatory_ok,
        notes=notes,
    )
