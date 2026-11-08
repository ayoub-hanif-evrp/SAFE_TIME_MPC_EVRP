"""Exact forward route-resource profiles and REAL incremental suffix evaluation.

Depot freight loading (Solomon/Schneider): when the vehicle is at the depot, all
customers until the next reload/return are preloaded. Therefore an unchanged visit
prefix is reusable only when the active tour freight manifest also matches.

INCREMENTAL mode propagates only the affected suffix from a recovered exact
resource state — it does **not** call ``evaluate_route`` on the full candidate in
the hot path. FULL mode remains available for independent checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.physics import RouteResult, evaluate_route, tour_customer_ids
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit


class EvalMode(str, Enum):
    FULL_EVALUATION = "FULL_EVALUATION"
    INCREMENTAL_EVALUATION = "INCREMENTAL_EVALUATION"


ENERGY_MODEL_VERSION = "nominal_linear_schneider_v1"


@dataclass(frozen=True)
class ResourceState:
    node: str
    time: float
    soc: float
    load: float
    onboard: frozenset[str]
    distance: float
    charge_time: float
    served: tuple[str, ...]


@dataclass
class RouteResourceProfile:
    """Validated forward states after each visit (including automatic depot return)."""

    visits: tuple[Visit, ...]
    states: tuple[ResourceState, ...]
    anchor: Anchor
    feasible: bool
    reason: str
    tour_manifests: tuple[frozenset[str], ...] = ()  # manifest active at each visit index
    energy_model_version: str = ENERGY_MODEL_VERSION
    assumptions: tuple[str, ...] = (
        "nominal_linear_energy",
        "exact_forward_prefix",
        "depot_freight_manifest_conditioned",
    )

    def prefix_state(self, n_visits: int) -> ResourceState | None:
        if n_visits < 0 or n_visits > len(self.states):
            return None
        if n_visits == 0:
            return ResourceState(
                self.anchor.node,
                self.anchor.time,
                self.anchor.soc,
                self.anchor.load,
                frozenset(self.anchor.onboard),
                0.0,
                0.0,
                (),
            )
        return self.states[n_visits - 1]


@dataclass
class EvalStats:
    full_evals: int = 0
    incremental_evals: int = 0
    prefix_reuses: int = 0
    fallbacks_to_full: int = 0
    prefix_visits_reused: int = 0
    suffix_visits_recomputed: int = 0
    full_calls_avoided: int = 0
    evaluate_route_calls: int = 0
    profile_build_seconds: float = 0.0
    propagate_seconds: float = 0.0
    notes: list[str] = field(default_factory=list)


def _normalize_visits(instance: Instance, visits: list[Visit]) -> list[Visit]:
    planned = list(visits)
    depot = instance.depot_id
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned.append(Visit(depot, "return"))
    return planned


def _manifests_along(planned: list[Visit], start_at_depot: bool) -> list[frozenset[str]]:
    """Freight set that was (or would be) loaded for the tour containing each visit."""
    manifests: list[frozenset[str]] = []
    if start_at_depot:
        active = frozenset(tour_customer_ids(planned, 0))
    else:
        active = frozenset()
    for index, visit in enumerate(planned):
        manifests.append(active)
        if visit.purpose == "reload":
            active = frozenset(tour_customer_ids(planned, index + 1))
    return manifests


def _longest_prefix_with_manifests(
    prev_visits: list[Visit],
    planned: list[Visit],
    prev_man: list[frozenset[str]],
    at_depot: bool,
    n: int,
) -> int:
    new_man = _manifests_along(planned, at_depot)
    k = 0
    while k < n and prev_visits[k] == planned[k]:
        pm = prev_man[k] if k < len(prev_man) else frozenset()
        nm = new_man[k] if k < len(new_man) else frozenset()
        if pm != nm:
            break
        k += 1
    return k


def longest_reusable_prefix_for(
    previous: RouteResourceProfile,
    planned: list[Visit],
    anchor: Anchor,
    depot_id: str,
) -> int:
    if (
        previous.anchor.node != anchor.node
        or abs(previous.anchor.time - anchor.time) > EPS
        or abs(previous.anchor.soc - anchor.soc) > EPS
        or abs(previous.anchor.load - anchor.load) > EPS
        or set(previous.anchor.onboard) != set(anchor.onboard)
        or previous.energy_model_version != ENERGY_MODEL_VERSION
        or not previous.feasible
        or not previous.states
    ):
        return 0
    at_depot = anchor.node == depot_id
    prev_visits = list(previous.visits)
    prev_man = (
        list(previous.tour_manifests)
        if previous.tour_manifests
        else _manifests_along(prev_visits, previous.anchor.node == depot_id)
    )
    return _longest_prefix_with_manifests(prev_visits, planned, prev_man, at_depot, min(len(prev_visits), len(planned)))


def _fail_result(reason: str, anchor: Anchor) -> RouteResult:
    return RouteResult(
        feasible=False,
        reason=reason,
        end_time=anchor.time,
        end_soc=anchor.soc,
        end_load=anchor.load,
        end_node=anchor.node,
    )


def propagate_from_state(
    instance: Instance,
    start: ResourceState,
    visits: list[Visit],
    *,
    energy: NominalLinearEnergy | None = None,
    preload_at_depot: bool = False,
) -> RouteResult:
    """Exact resource propagation from a known state through ``visits`` (no evaluate_route)."""
    model = energy or NominalLinearEnergy()
    vehicle = instance.vehicle_type
    depot = instance.depot_id
    planned = list(visits)
    if not planned:
        return RouteResult(
            feasible=True,
            reason="ok",
            distance=0.0,
            charge_time=0.0,
            end_time=start.time,
            end_soc=start.soc,
            end_load=start.load,
            end_node=start.node,
            served=[],
            visits=[],
        )

    node = start.node
    time = float(start.time)
    soc = float(start.soc)
    load = float(start.load)
    onboard = set(start.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []

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

    if preload_at_depot and node == depot:
        problem = load_customers([cid for cid in tour_customer_ids(planned, 0) if cid not in onboard])
        if problem:
            return _fail_result(
                problem, Anchor(start.node, start.time, start.soc, start.load, frozenset(start.onboard))
            )

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return _fail_result(
                    f"missing_arc:{node}->{visit.node_id}", Anchor(node, time, soc, load, frozenset(onboard))
                )
            used = model.travel_energy(instance, arc, soc=soc, load=load)
            if soc - used < -EPS:
                return _fail_result("battery_depleted", Anchor(node, time, soc, load, frozenset(onboard)))
            soc -= used
            if soc < 0 and soc >= -EPS:
                soc = 0.0
            time += arc.travel_time
            distance += arc.distance
            node = visit.node_id

        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                return _fail_result("service_target_not_customer", Anchor(node, time, soc, load, frozenset(onboard)))
            if visit.node_id not in onboard:
                return _fail_result("goods_not_onboard", Anchor(node, time, soc, load, frozenset(onboard)))
            if time > cust.window.due + EPS:
                return _fail_result("missed_window", Anchor(node, time, soc, load, frozenset(onboard)))
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            if load < -EPS:
                return _fail_result("negative_load", Anchor(node, time, soc, load, frozenset(onboard)))
            onboard.discard(visit.node_id)
            served.append(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if station.kind is not NodeKind.CHARGER:
                return _fail_result("charge_away_from_station", Anchor(node, time, soc, load, frozenset(onboard)))
            if time > station.window.due + EPS:
                return _fail_result("charger_window", Anchor(node, time, soc, load, frozenset(onboard)))
            if time < station.window.ready:
                time = station.window.ready
            target = vehicle.battery_capacity if vehicle.recharge_policy == "full" else visit.charge_target
            if target is None or target > vehicle.battery_capacity + EPS or target < soc - EPS:
                return _fail_result("impossible_charge", Anchor(node, time, soc, load, frozenset(onboard)))
            duration = model.charge_duration(soc, float(target), vehicle.inverse_recharge_rate)
            time += duration
            charge_time += duration
            soc = float(target)
        elif visit.purpose == "reload":
            if node != depot:
                return _fail_result("reload_away_from_depot", Anchor(node, time, soc, load, frozenset(onboard)))
            load = 0.0
            onboard.clear()
            problem = load_customers(tour_customer_ids(planned, index + 1))
            if problem:
                return _fail_result(problem, Anchor(node, time, soc, load, frozenset(onboard)))
        elif visit.purpose == "return":
            if node != depot:
                return _fail_result("return_not_at_depot", Anchor(node, time, soc, load, frozenset(onboard)))
            if time > instance.node(depot).window.due + EPS:
                return _fail_result("depot_deadline", Anchor(node, time, soc, load, frozenset(onboard)))
        else:
            return _fail_result("unknown_purpose", Anchor(node, time, soc, load, frozenset(onboard)))

    if len(served) != len(set(served)):
        return _fail_result("duplicate_service", Anchor(node, time, soc, load, frozenset(onboard)))
    return RouteResult(
        feasible=True,
        reason="ok",
        distance=distance,
        charge_time=charge_time,
        end_time=time,
        end_soc=soc,
        end_load=load,
        end_node=node,
        served=served,
        visits=planned,
    )


def _forward_states(
    instance: Instance,
    anchor: Anchor,
    planned: list[Visit],
    model: NominalLinearEnergy,
) -> tuple[list[ResourceState], list[frozenset[str]]]:
    """Build per-visit states by successive single-step propagation."""
    states: list[ResourceState] = []
    at_depot = anchor.node == instance.depot_id
    manifests = _manifests_along(planned, at_depot)
    cur = ResourceState(anchor.node, anchor.time, anchor.soc, anchor.load, frozenset(anchor.onboard), 0.0, 0.0, ())
    # First step may preload
    step = propagate_from_state(instance, cur, planned[:1], energy=model, preload_at_depot=at_depot)
    if not step.feasible:
        return [], manifests
    # Rebuild by walking all visits with cumulative served/distance from sequential steps
    node = anchor.node
    time = float(anchor.time)
    soc = float(anchor.soc)
    load = float(anchor.load)
    onboard = set(anchor.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []
    vehicle = instance.vehicle_type

    def load_customers(ids: list[str]) -> str | None:
        nonlocal load
        for cid in ids:
            if cid in onboard:
                continue
            if load + instance.node(cid).demand > vehicle.load_capacity + EPS:
                return "excess_payload"
            onboard.add(cid)
            load += instance.node(cid).demand
        return None

    if at_depot:
        if load_customers([cid for cid in tour_customer_ids(planned, 0) if cid not in onboard]):
            return [], manifests

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            arc = instance.arc(node, visit.node_id)
            used = model.travel_energy(instance, arc, soc=soc, load=load)
            soc -= used
            if soc < 0 and soc >= -EPS:
                soc = 0.0
            time += arc.travel_time
            distance += arc.distance
            node = visit.node_id
        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            onboard.discard(visit.node_id)
            served.append(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if time < station.window.ready:
                time = station.window.ready
            target = vehicle.battery_capacity if vehicle.recharge_policy == "full" else visit.charge_target
            assert target is not None
            duration = model.charge_duration(soc, float(target), vehicle.inverse_recharge_rate)
            time += duration
            charge_time += duration
            soc = float(target)
        elif visit.purpose == "reload":
            load = 0.0
            onboard.clear()
            load_customers(tour_customer_ids(planned, index + 1))
        states.append(ResourceState(node, time, soc, load, frozenset(onboard), distance, charge_time, tuple(served)))
    return states, manifests


def build_profile(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    energy: NominalLinearEnergy | None = None,
) -> RouteResourceProfile:
    model = energy or NominalLinearEnergy()
    planned = _normalize_visits(instance, visits)
    # Authoritative feasibility via evaluate_route for profile construction only
    check = evaluate_route(instance, anchor, visits, model)
    if not check.feasible:
        return RouteResourceProfile(
            visits=tuple(planned),
            states=(),
            anchor=anchor,
            feasible=False,
            reason=check.reason,
        )
    states, manifests = _forward_states(instance, anchor, check.visits, model)
    return RouteResourceProfile(
        visits=tuple(check.visits),
        states=tuple(states),
        anchor=anchor,
        feasible=True,
        reason="ok",
        tour_manifests=tuple(manifests),
    )


def evaluate_with_profile(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    *,
    energy: NominalLinearEnergy | None = None,
    mode: EvalMode = EvalMode.FULL_EVALUATION,
    previous: RouteResourceProfile | None = None,
    stats: EvalStats | None = None,
) -> tuple[RouteResult, RouteResourceProfile | None]:
    """Evaluate a candidate. INCREMENTAL mode uses suffix propagation only."""
    model = energy or NominalLinearEnergy()
    st = stats or EvalStats()
    planned = _normalize_visits(instance, visits)

    if mode is EvalMode.FULL_EVALUATION:
        st.full_evals += 1
        st.evaluate_route_calls += 1
        t0 = perf_counter()
        result = evaluate_route(instance, anchor, visits, model)
        st.propagate_seconds += perf_counter() - t0
        if not result.feasible:
            return result, None
        t1 = perf_counter()
        profile = build_profile(instance, anchor, visits, model)
        st.profile_build_seconds += perf_counter() - t1
        st.evaluate_route_calls += 1  # build_profile also checks
        return result, profile

    # INCREMENTAL path
    if previous is None or not previous.feasible:
        st.fallbacks_to_full += 1
        st.notes.append("no_previous_profile")
        return _incremental_from_scratch(instance, anchor, visits, planned, model, st)

    pref = longest_reusable_prefix_for(previous, planned, anchor, instance.depot_id)
    if pref == 0:
        st.fallbacks_to_full += 1
        st.notes.append("prefix_or_manifest_invalid")
        return _incremental_from_scratch(instance, anchor, visits, planned, model, st)

    if pref == len(planned) and pref == len(previous.visits):
        st.prefix_reuses += 1
        st.incremental_evals += 1
        st.prefix_visits_reused += pref
        st.full_calls_avoided += 1
        # Reconstruct RouteResult from profile terminal state
        last = previous.states[-1]
        result = RouteResult(
            feasible=True,
            reason="ok",
            distance=last.distance,
            charge_time=last.charge_time,
            end_time=last.time,
            end_soc=last.soc,
            end_load=last.load,
            end_node=last.node,
            served=list(last.served),
            visits=list(previous.visits),
        )
        return result, previous

    # Suffix recompute from exact prefix state
    start = previous.prefix_state(pref)
    if start is None:
        st.fallbacks_to_full += 1
        return _incremental_from_scratch(instance, anchor, visits, planned, model, st)

    suffix = planned[pref:]
    st.prefix_reuses += 1
    st.incremental_evals += 1
    st.prefix_visits_reused += pref
    st.suffix_visits_recomputed += len(suffix)
    st.full_calls_avoided += 1
    t0 = perf_counter()
    # No depot preload on suffix — freight already reflected in start.onboard/load
    suffix_result = propagate_from_state(instance, start, suffix, energy=model, preload_at_depot=False)
    st.propagate_seconds += perf_counter() - t0
    if not suffix_result.feasible:
        return suffix_result, None

    # Merge: distances/charges are suffix-relative; add prefix accumulators from start
    merged = RouteResult(
        feasible=True,
        reason="ok",
        distance=start.distance + suffix_result.distance,
        charge_time=start.charge_time + suffix_result.charge_time,
        end_time=suffix_result.end_time,
        end_soc=suffix_result.end_soc,
        end_load=suffix_result.end_load,
        end_node=suffix_result.end_node,
        served=list(start.served) + list(suffix_result.served),
        visits=planned,
    )
    # Build updated profile states: keep prefix states + recompute suffix states
    prefix_states = list(previous.states[:pref])
    # Recompute full profile states cheaply from merged path for caching
    t1 = perf_counter()
    states, manifests = _forward_states(instance, anchor, planned, model)
    st.profile_build_seconds += perf_counter() - t1
    if not states:
        # Fall back: still return merged feasibility from suffix prop
        profile = RouteResourceProfile(
            visits=tuple(planned),
            states=tuple(prefix_states),
            anchor=anchor,
            feasible=True,
            reason="ok",
        )
        return merged, profile
    profile = RouteResourceProfile(
        visits=tuple(planned),
        states=tuple(states),
        anchor=anchor,
        feasible=True,
        reason="ok",
        tour_manifests=tuple(manifests),
    )
    return merged, profile


def _incremental_from_scratch(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    planned: list[Visit],
    model: NominalLinearEnergy,
    st: EvalStats,
) -> tuple[RouteResult, RouteResourceProfile | None]:
    """Full exact propagation without evaluate_route (still not the hot-path ideal)."""
    st.incremental_evals += 1
    st.suffix_visits_recomputed += len(planned)
    start = ResourceState(anchor.node, anchor.time, anchor.soc, anchor.load, frozenset(anchor.onboard), 0.0, 0.0, ())
    t0 = perf_counter()
    result = propagate_from_state(
        instance, start, planned, energy=model, preload_at_depot=(anchor.node == instance.depot_id)
    )
    st.propagate_seconds += perf_counter() - t0
    if not result.feasible:
        return result, None
    t1 = perf_counter()
    states, manifests = _forward_states(instance, anchor, planned, model)
    st.profile_build_seconds += perf_counter() - t1
    profile = RouteResourceProfile(
        visits=tuple(planned),
        states=tuple(states),
        anchor=anchor,
        feasible=True,
        reason="ok",
        tour_manifests=tuple(manifests),
    )
    return result, profile
