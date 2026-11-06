"""Bounded deterministic insertion. An incumbent is improved only by certified candidates."""

from __future__ import annotations

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.optimization.insertion import _variants
from safe_time_evrp.robust.backup import dispatch_suffix
from safe_time_evrp.robust.certificate import Verdict, certify_routes
from safe_time_evrp.robust.uncertainty import RectangularUncertainty


def _strip_return(instance: Instance, visits: list[Visit]) -> list[Visit]:
    if visits and visits[-1].purpose == "return" and visits[-1].node_id == instance.depot_id:
        return list(visits[:-1])
    return list(visits)


def improve(
    instance: Instance,
    observation: Observation,
    incumbent: dict[str, list[Visit]],
    uncertainty: RectangularUncertainty,
    *,
    steps: int,
    horizon: float,
    allowed_customers: frozenset[str] | None = None,
):
    """Yield certified fleet plans. At most ``steps`` insertion attempts are made.

    ``horizon`` is accepted for API compatibility with the supervisor payload. This
    legacy insertion loop does not implement a multi-stage predictive horizon; Gate 3A
    moves true multistage planning into ``safe_time_evrp.multistage``.
    """
    _ = horizon  # intentionally unused by this constructive baseline
    visible = allowed_customers
    if visible is None:
        visible = (
            frozenset(observation.released_open)
            | frozenset(observation.accepted)
            | frozenset(observation.in_service)
            | frozenset(observation.completed)
        )
    routes = {}
    for vehicle in observation.vehicles:
        routes[vehicle.id] = _strip_return(
            instance,
            dispatch_suffix(
                list(incumbent.get(vehicle.id, [])),
                observation,
                vehicle.anchor.node,
                vehicle.anchor.soc,
                instance.vehicle_type.battery_capacity,
            ),
        )
    covered = {visit.node_id for visits in routes.values() for visit in visits if visit.purpose == "service"}
    mandatory = [cid for cid in observation.accepted if cid not in covered and cid in visible]
    optional = [
        cid
        for cid in observation.released_open
        if cid in visible
        and cid not in observation.accepted
        and cid not in observation.completed
        and cid not in covered
    ]
    queue = mandatory + optional
    examined = 0
    accepted: list[str] = []
    rejected: list[str] = []
    attempts = 0
    for customer_id in queue:
        if attempts >= steps and customer_id not in mandatory:
            break
        attempts += 1
        examined += 1
        placed = _place(instance, observation, routes, customer_id, uncertainty)
        if placed:
            if customer_id not in observation.accepted:
                accepted.append(customer_id)
            required = tuple(observation.accepted) + tuple(cid for cid in accepted if cid not in observation.accepted)
            certificate = certify_routes(instance, observation, routes, uncertainty, required=required)
            yield {
                "routes": {vid: list(visits) for vid, visits in routes.items()},
                "newly_accepted": list(accepted),
                "rejected": list(rejected),
                "examined": examined,
                "certificate_ok": certificate.verdict is Verdict.CERTIFIED_FEASIBLE,
                "final": False,
            }
        else:
            if customer_id in observation.accepted:
                yield {
                    "routes": {vid: list(visits) for vid, visits in routes.items()},
                    "newly_accepted": list(accepted),
                    "rejected": rejected + [customer_id],
                    "examined": examined,
                    "certificate_ok": False,
                    "commitment_failed": customer_id,
                    "final": True,
                }
                return
            rejected.append(customer_id)
    required = tuple(list(observation.accepted) + accepted)
    certificate = certify_routes(instance, observation, routes, uncertainty, required=required)
    yield {
        "routes": {vid: list(visits) for vid, visits in routes.items()},
        "newly_accepted": list(accepted),
        "rejected": list(rejected),
        "examined": examined,
        "certificate_ok": certificate.verdict is Verdict.CERTIFIED_FEASIBLE,
        "final": True,
    }


def _place(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    customer_id: str,
    uncertainty: RectangularUncertainty,
) -> bool:
    stations = instance.charger_ids()
    best_key: tuple[float, str, int] | None = None
    best: tuple[str, list[Visit]] | None = None
    for vehicle in observation.vehicles:
        route = routes[vehicle.id]
        for pos in range(len(route) + 1):
            for candidate in _variants(route, pos, customer_id, stations, instance.depot_id):
                certificate = certify_routes(
                    instance,
                    _solo(observation, vehicle.id),
                    {vehicle.id: candidate},
                    uncertainty,
                    required=(),
                )
                if certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
                    continue
                if not any(visit.node_id == customer_id and visit.purpose == "service" for visit in candidate):
                    continue
                key = (certificate.time_margin if certificate.time_margin is not None else 0.0, vehicle.id, pos)
                # Larger time margin is better. Sort by the negative margin.
                rank = (-key[0], key[1], key[2])
                if best_key is None or rank < best_key:
                    best_key = rank
                    best = (vehicle.id, candidate)
    if best is None:
        return False
    routes[best[0]] = _strip_return(instance, best[1])
    return True


def _solo(observation: Observation, vehicle_id: str) -> Observation:
    vehicle = next(item for item in observation.vehicles if item.id == vehicle_id)
    return Observation(
        time=observation.time,
        vehicles=(vehicle,),
        released_open=observation.released_open,
        accepted=(),
        completed=observation.completed,
        rejected=observation.rejected,
        in_service=observation.in_service,
        deferred=observation.deferred,
    )
