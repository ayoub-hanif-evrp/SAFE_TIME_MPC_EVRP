"""Worst-case route certificate for a fixed sequence under rectangular bounds.

For full recharge on the Schneider linear model the upper corner is necessary and
sufficient. Fixed-target partial charging is not monotone in energy: a lower energy
realization can raise arrival SOC above the written target. That case returns
UNKNOWN rather than a false feasible label. A failed search is never labeled infeasible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter

from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Observation, Visit
from safe_time_evrp.robust.uncertainty import RectangularUncertainty, scale_instance


class Verdict(str, Enum):
    CERTIFIED_FEASIBLE = "certified_feasible"
    CERTIFIED_INFEASIBLE = "certified_infeasible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PrefixState:
    index: int
    node: str
    time: float
    soc: float
    load: float
    onboard: frozenset[str]


@dataclass
class Certificate:
    verdict: Verdict
    assumptions: tuple[str, ...]
    validity: tuple[str, ...]
    energy_margin: float | None
    time_margin: float | None
    critical_constraint: str
    runtime_seconds: float
    witness: dict
    prefixes: tuple[PrefixState, ...] = ()
    model: str = "schneider_linear_rectangle"


_VALIDITY = (
    "The visit sequence and charge targets stay fixed.",
    "Every realized arc factor stays inside the rectangle.",
    "Exact upper-corner equivalence requires full recharge (or degenerate energy bounds).",
    "No station closure, queue, or nonlinear charge is present.",
    "Payload and service durations stay at their nominal values.",
)

PLANT_MODEL_VERSION = "schneider_linear_v1"


def _unknown(reason: str, uncertainty: RectangularUncertainty, started: float) -> Certificate:
    return Certificate(
        verdict=Verdict.UNKNOWN,
        assumptions=uncertainty.assumptions,
        validity=_VALIDITY,
        energy_margin=None,
        time_margin=None,
        critical_constraint=reason,
        runtime_seconds=perf_counter() - started,
        witness={"reason": reason},
    )


def _with_return(instance: Instance, visits: list[Visit]) -> list[Visit]:
    depot = instance.depot_id
    planned = list(visits)
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned.append(Visit(depot, "return"))
    return planned


def propagate(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    uncertainty: RectangularUncertainty,
    *,
    energy_inflation: float = 1.0,
) -> Certificate:
    """Propagate the upper time and upper energy corner of a fixed sequence.

    ``energy_inflation`` greater than one is a sufficient tightening. It is not the
    exact rectangle. Callers that want the exact test must leave it at 1.
    """
    started = perf_counter()
    if not uncertainty.monotone_linear:
        return _unknown("nonmonotone_dynamics", uncertainty, started)
    if energy_inflation < 1.0:
        return _unknown("inflation_below_one", uncertainty, started)
    vehicle = instance.vehicle_type
    if vehicle.recharge_policy not in {"full", "partial"}:
        return _unknown("unsupported_recharge_policy", uncertainty, started)

    planned = _with_return(instance, visits)
    if vehicle.recharge_policy == "partial" and uncertainty.energy_lower + EPS < uncertainty.energy_upper:
        if any(visit.purpose == "charge" for visit in planned):
            return _unknown("fixed_partial_target_not_monotone", uncertainty, started)
    node = anchor.node
    time = anchor.time
    soc = anchor.soc
    load = anchor.load
    onboard = set(anchor.onboard)
    energy_margin = float("inf")
    time_margin = float("inf")
    prefixes: list[PrefixState] = []
    time_factor = uncertainty.time_upper
    energy_factor = uncertainty.energy_upper * energy_inflation
    assumptions = uncertainty.assumptions
    if energy_inflation > 1.0:
        assumptions = assumptions + (f"Sufficient energy inflation {energy_inflation}.",)

    def finish(verdict: Verdict, reason: str, witness: dict | None = None) -> Certificate:
        return Certificate(
            verdict=verdict,
            assumptions=assumptions,
            validity=_VALIDITY,
            energy_margin=None if energy_margin == float("inf") else energy_margin,
            time_margin=None if time_margin == float("inf") else time_margin,
            critical_constraint=reason,
            runtime_seconds=perf_counter() - started,
            witness=witness or {"node": node, "time": time, "soc": soc},
            prefixes=tuple(prefixes),
            model="tightened_rectangle" if energy_inflation > 1.0 else "schneider_linear_rectangle",
        )

    def load_customers(ids: list[str]) -> str | None:
        nonlocal load
        extra = 0.0
        for cid in ids:
            if cid in onboard:
                continue
            cust = instance.node(cid)
            if cust.kind is not NodeKind.CUSTOMER:
                return "service_target_not_customer"
            extra += cust.demand
        if load + extra > vehicle.load_capacity + EPS:
            return "excess_payload"
        for cid in ids:
            if cid not in onboard:
                onboard.add(cid)
                load += instance.node(cid).demand
        return None

    def tour_ids(start: int) -> list[str]:
        chosen: list[str] = []
        for visit in planned[start:]:
            if visit.purpose in {"reload", "return"}:
                break
            if visit.purpose == "service":
                chosen.append(visit.node_id)
        return chosen

    if node == instance.depot_id:
        problem = load_customers(tour_ids(0))
        if problem:
            return finish(Verdict.CERTIFIED_INFEASIBLE, problem)

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return finish(Verdict.CERTIFIED_INFEASIBLE, f"missing_arc:{node}->{visit.node_id}")
            used = energy_factor * arc.energy
            if soc - used < uncertainty.soc_floor - EPS:
                return finish(
                    Verdict.CERTIFIED_INFEASIBLE,
                    "battery_floor",
                    {"arc": f"{node}->{visit.node_id}", "soc": soc, "used": used},
                )
            soc -= used
            energy_margin = min(energy_margin, soc - uncertainty.soc_floor)
            time += time_factor * arc.travel_time
            node = visit.node_id

        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "service_target_not_customer")
            if visit.node_id not in onboard:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "goods_not_onboard")
            if time > cust.window.due + EPS:
                return finish(
                    Verdict.CERTIFIED_INFEASIBLE,
                    "missed_window",
                    {"customer": visit.node_id, "arrival": time, "due": cust.window.due},
                )
            start = max(time, cust.window.ready)
            time_margin = min(time_margin, cust.window.due - start)
            time = start + cust.service_time
            load -= cust.demand
            onboard.discard(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if station.kind is not NodeKind.CHARGER:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "charge_away_from_station")
            if time > station.window.due + EPS:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "charger_window")
            if time < station.window.ready:
                time = station.window.ready
            if vehicle.recharge_policy == "full":
                target = vehicle.battery_capacity
            else:
                if visit.charge_target is None:
                    return _unknown("partial_charge_missing_target", uncertainty, started)
                target = visit.charge_target
            if target > vehicle.battery_capacity + EPS or target < soc - EPS:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "impossible_charge")
            time += vehicle.inverse_recharge_rate * max(0.0, target - soc)
            soc = target
        elif visit.purpose == "reload":
            if node != instance.depot_id:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "reload_away_from_depot")
            depot = instance.node(instance.depot_id)
            if time > depot.window.due + EPS:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "depot_window")
            if time < depot.window.ready:
                time = depot.window.ready
            load = 0.0
            onboard.clear()
            problem = load_customers(tour_ids(index + 1))
            if problem:
                return finish(Verdict.CERTIFIED_INFEASIBLE, problem)
        elif visit.purpose == "return":
            if node != instance.depot_id:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "return_not_at_depot")
            due = instance.node(instance.depot_id).window.due
            if time > due + EPS:
                return finish(Verdict.CERTIFIED_INFEASIBLE, "depot_deadline", {"time": time, "due": due})
            time_margin = min(time_margin, due - time)
        else:
            return _unknown("unknown_purpose", uncertainty, started)
        prefixes.append(PrefixState(index, node, time, soc, load, frozenset(onboard)))

    return finish(Verdict.CERTIFIED_FEASIBLE, "ok")


def certify_routes(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    uncertainty: RectangularUncertainty,
    *,
    required: tuple[str, ...] | None = None,
    energy_inflation: float = 1.0,
) -> Certificate:
    """Certify a fleet plan. Missing an accepted customer is proved infeasible."""
    started = perf_counter()
    must = tuple(observation.accepted if required is None else required)
    served: list[str] = []
    margins_e: list[float] = []
    margins_t: list[float] = []
    prefixes: list[PrefixState] = []
    by_id = {vehicle.id: vehicle for vehicle in observation.vehicles}
    unknown_keys = set(routes) - set(by_id)
    if unknown_keys:
        return Certificate(
            verdict=Verdict.CERTIFIED_INFEASIBLE,
            assumptions=uncertainty.assumptions,
            validity=_VALIDITY,
            energy_margin=None,
            time_margin=None,
            critical_constraint="illegal_vehicle_assignment",
            runtime_seconds=perf_counter() - started,
            witness={"unknown_vehicles": sorted(unknown_keys)},
        )
    for vehicle_id, vehicle in by_id.items():
        certificate = propagate(
            instance,
            vehicle.anchor,
            list(routes.get(vehicle_id, [])),
            uncertainty,
            energy_inflation=energy_inflation,
        )
        if certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
            certificate.runtime_seconds = perf_counter() - started
            return certificate
        if certificate.energy_margin is not None:
            margins_e.append(certificate.energy_margin)
        if certificate.time_margin is not None:
            margins_t.append(certificate.time_margin)
        prefixes.extend(certificate.prefixes)
        for visit in _with_return(instance, list(routes.get(vehicle_id, []))):
            if visit.purpose == "service":
                served.append(visit.node_id)
    if len(served) != len(set(served)):
        dupes = sorted({cid for cid in served if served.count(cid) > 1})
        return Certificate(
            verdict=Verdict.CERTIFIED_INFEASIBLE,
            assumptions=uncertainty.assumptions,
            validity=_VALIDITY,
            energy_margin=min(margins_e) if margins_e else None,
            time_margin=min(margins_t) if margins_t else None,
            critical_constraint="duplicate_service",
            runtime_seconds=perf_counter() - started,
            witness={"duplicates": dupes},
            prefixes=tuple(prefixes),
        )
    missing = [cid for cid in must if cid not in served]
    if missing:
        return Certificate(
            verdict=Verdict.CERTIFIED_INFEASIBLE,
            assumptions=uncertainty.assumptions,
            validity=_VALIDITY,
            energy_margin=min(margins_e) if margins_e else None,
            time_margin=min(margins_t) if margins_t else None,
            critical_constraint="commitment_omitted",
            runtime_seconds=perf_counter() - started,
            witness={"missing": missing},
            prefixes=tuple(prefixes),
        )
    return Certificate(
        verdict=Verdict.CERTIFIED_FEASIBLE,
        assumptions=uncertainty.assumptions,
        validity=_VALIDITY,
        energy_margin=min(margins_e) if margins_e else None,
        time_margin=min(margins_t) if margins_t else None,
        critical_constraint="ok",
        runtime_seconds=perf_counter() - started,
        witness={"served": served},
        prefixes=tuple(prefixes),
    )


def upper_corner_feasible(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    uncertainty: RectangularUncertainty,
) -> bool:
    """Independent check: Part 1 physics on arc tables scaled to the upper corner."""
    scaled = scale_instance(
        instance,
        time_factor=uncertainty.time_upper,
        energy_factor=uncertainty.energy_upper,
    )
    result = evaluate_route(scaled, anchor, list(visits))
    if not result.feasible:
        return False
    return result.end_soc >= uncertainty.soc_floor - EPS


def certify(
    *,
    observed_state: Observation,
    committed_routes: dict[str, list[Visit]],
    uncertainty_set: RectangularUncertainty,
    instance: Instance,
    required: tuple[str, ...] | None = None,
) -> Certificate:
    """Public certificate entry point."""
    return certify_routes(
        instance,
        observed_state,
        committed_routes,
        uncertainty_set,
        required=required,
    )


def _route_signature(instance: Instance, visits: list[Visit]) -> tuple[str, ...]:
    planned = _with_return(instance, visits)
    return tuple(f"{visit.node_id}:{visit.purpose}:{visit.charge_target}" for visit in planned)


def cache_validity_key(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    uncertainty: RectangularUncertainty,
    *,
    energy_inflation: float = 1.0,
) -> tuple:
    """Every parameter that can invalidate a cached prefix."""
    return (
        PLANT_MODEL_VERSION,
        instance.name,
        instance.source_format,
        instance.vehicle_type.recharge_policy,
        instance.vehicle_type.battery_capacity,
        instance.vehicle_type.inverse_recharge_rate,
        instance.vehicle_type.load_capacity,
        anchor,
        uncertainty.time_lower,
        uncertainty.time_upper,
        uncertainty.energy_lower,
        uncertainty.energy_upper,
        uncertainty.soc_floor,
        uncertainty.monotone_linear,
        energy_inflation,
        _route_signature(instance, visits),
    )


@dataclass
class IncrementalCache:
    validity_key: tuple = ()
    signature: tuple[str, ...] = ()
    prefixes: tuple[PrefixState, ...] = ()
    hits: int = 0
    misses: int = 0
    full_seconds: float = 0.0
    incremental_seconds: float = 0.0


def propagate_incremental(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    uncertainty: RectangularUncertainty,
    cache: IncrementalCache,
    *,
    energy_inflation: float = 1.0,
) -> Certificate:
    """Reuse a certified prefix when only a suffix of the same sequence changes.

    The cache is keyed by route, charge targets, uncertainty, anchor and plant model.
    This is a standard prefix cache, not a new extension function.
    """
    planned = _with_return(instance, visits)
    signature = _route_signature(instance, visits)
    key = cache_validity_key(instance, anchor, visits, uncertainty, energy_inflation=energy_inflation)
    context = key[:-1]  # drop the route signature; compare separately
    cached_context = cache.validity_key[:-1] if cache.validity_key else ()
    match = 0
    if cached_context == context and cache.prefixes:
        limit = min(len(signature), len(cache.signature), len(cache.prefixes))
        while match < limit and signature[match] == cache.signature[match]:
            match += 1
    if match > 0:
        started = perf_counter()
        state = cache.prefixes[match - 1]
        suffix_anchor = Anchor(state.node, state.time, state.soc, state.load, state.onboard)
        certificate = propagate(
            instance,
            suffix_anchor,
            planned[match:],
            uncertainty,
            energy_inflation=energy_inflation,
        )
        certificate.runtime_seconds = perf_counter() - started
        cache.hits += 1
        cache.incremental_seconds += certificate.runtime_seconds
        return certificate
    certificate = propagate(instance, anchor, visits, uncertainty, energy_inflation=energy_inflation)
    cache.misses += 1
    cache.full_seconds += certificate.runtime_seconds
    cache.signature = signature
    cache.prefixes = certificate.prefixes
    cache.validity_key = key
    return certificate
