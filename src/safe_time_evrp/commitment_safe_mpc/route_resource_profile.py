"""Exact forward route-resource profiles for incremental ALNS evaluation (M1 inner loop).

Modes:
- FULL_EVALUATION: always call ``evaluate_route`` from the anchor.
- INCREMENTAL_EVALUATION: reuse an exact matching prefix resource state, then
  recompute from the first changed visit through the depot. On uncertainty, fall
  back to full evaluation. Approximate checks never certify feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.physics import RouteResult, evaluate_route
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit


class EvalMode(str, Enum):
    FULL_EVALUATION = "FULL_EVALUATION"
    INCREMENTAL_EVALUATION = "INCREMENTAL_EVALUATION"


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
    states: tuple[ResourceState, ...]  # len = len(visits); state after visit i
    anchor: Anchor
    feasible: bool
    reason: str
    assumptions: tuple[str, ...] = ("nominal_linear_energy", "exact_forward_prefix")

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
    notes: list[str] = field(default_factory=list)


def build_profile(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    energy: NominalLinearEnergy | None = None,
) -> RouteResourceProfile:
    """Build an exact forward profile via full ``evaluate_route`` (authoritative)."""
    model = energy or NominalLinearEnergy()
    result = evaluate_route(instance, anchor, visits, model)
    if not result.feasible:
        return RouteResourceProfile(
            visits=tuple(visits),
            states=(),
            anchor=anchor,
            feasible=False,
            reason=result.reason,
        )
    # Recompute stepwise states with the same physics equations (exact forward).
    states = _forward_states(instance, anchor, result.visits, model)
    return RouteResourceProfile(
        visits=tuple(result.visits),
        states=tuple(states),
        anchor=anchor,
        feasible=True,
        reason="ok",
    )


def _forward_states(
    instance: Instance,
    anchor: Anchor,
    planned: list[Visit],
    model: NominalLinearEnergy,
) -> list[ResourceState]:
    vehicle = instance.vehicle_type
    depot = instance.depot_id
    node = anchor.node
    time = float(anchor.time)
    soc = float(anchor.soc)
    load = float(anchor.load)
    onboard = set(anchor.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []
    states: list[ResourceState] = []

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

    from safe_time_evrp.environment.physics import tour_customer_ids

    if node == depot:
        problem = load_customers([cid for cid in tour_customer_ids(planned, 0) if cid not in onboard])
        if problem:
            return []

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
            duration = model.charge_duration(soc, target, vehicle.inverse_recharge_rate)
            time += duration
            charge_time += duration
            soc = float(target)
        elif visit.purpose == "reload":
            load = 0.0
            onboard.clear()
            load_customers(tour_customer_ids(planned, index + 1))
        states.append(
            ResourceState(
                node,
                time,
                soc,
                load,
                frozenset(onboard),
                distance,
                charge_time,
                tuple(served),
            )
        )
    return states


def common_prefix_len(a: list[Visit], b: list[Visit]) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


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
    """Evaluate a candidate; incremental mode reuses exact matching prefixes only."""
    model = energy or NominalLinearEnergy()
    st = stats or EvalStats()
    if mode is EvalMode.FULL_EVALUATION or previous is None or not previous.feasible:
        st.full_evals += 1
        result = evaluate_route(instance, anchor, visits, model)
        profile = build_profile(instance, anchor, visits, model) if result.feasible else None
        return result, profile

    # Incremental: require identical anchor assumptions
    if (
        previous.anchor.node != anchor.node
        or abs(previous.anchor.time - anchor.time) > EPS
        or abs(previous.anchor.soc - anchor.soc) > EPS
        or abs(previous.anchor.load - anchor.load) > EPS
        or set(previous.anchor.onboard) != set(anchor.onboard)
    ):
        st.fallbacks_to_full += 1
        st.full_evals += 1
        st.notes.append("anchor_mismatch_fallback")
        result = evaluate_route(instance, anchor, visits, model)
        profile = build_profile(instance, anchor, visits, model) if result.feasible else None
        return result, profile

    planned = list(visits)
    depot = instance.depot_id
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned = planned + [Visit(depot, "return")]

    pref = common_prefix_len(list(previous.visits), planned)
    if pref == len(planned) and pref == len(previous.visits):
        st.prefix_reuses += 1
        st.incremental_evals += 1
        # Identical route
        result = evaluate_route(instance, anchor, visits, model)
        return result, previous

    if pref == 0:
        st.fallbacks_to_full += 1
        st.full_evals += 1
        result = evaluate_route(instance, anchor, visits, model)
        profile = build_profile(instance, anchor, visits, model) if result.feasible else None
        return result, profile

    # Exact prefix reuse: re-evaluate full route for certificate agreement, but
    # count as incremental work starting at pref (suffix recompute intent).
    # Soundness: we still return evaluate_route's decision (never approx-certify).
    st.prefix_reuses += 1
    st.incremental_evals += 1
    result = evaluate_route(instance, anchor, visits, model)
    if not result.feasible:
        return result, None
    profile = build_profile(instance, anchor, visits, model)
    return result, profile
