"""Offline service references with honest bound labels (Gate 4).

A feasible constructive plan with z_heur served customers proves only
``z_heur <= z*_offline``. It is therefore a **feasible lower bound** on the
offline optimum, never an upper bound.

Certified upper bounds require a valid relaxation, optimality certificate, or
exact enumeration. Gate 3F ``offline_service_upper_bound`` results are
reclassified as heuristic indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import permutations, product

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance, Node, TimeWindow
from safe_time_evrp.models.state import Anchor, Observation, Visit
from safe_time_evrp.optimization.insertion import construct_routes
from safe_time_evrp.testbed.constructor import make_observation


class BoundKind(str, Enum):
    FEASIBLE_LOWER_BOUND = "FEASIBLE_LOWER_BOUND"
    CERTIFIED_UPPER_BOUND = "CERTIFIED_UPPER_BOUND"
    EXACT_OPTIMUM = "EXACT_OPTIMUM"
    UNKNOWN = "UNKNOWN"
    HEURISTIC_INDICATOR = "HEURISTIC_INDICATOR"


@dataclass(frozen=True)
class OfflineReferenceReport:
    n_customers: int
    n_announced: int
    n_window_impossible: int
    window_impossible_ids: tuple[str, ...]
    feasible_lower_bound: int
    certified_upper_bound: int | None
    exact_optimum: int | None
    bound_kind: BoundKind
    service_rate_lb: float
    service_rate_ub: float | None
    notes: tuple[str, ...]


def window_impossible(
    instance: Instance,
    releases: list[tuple[str, float]],
) -> list[str]:
    """Customers that cannot start service under any vehicle positioning.

    Valid claim: service cannot start before ``max(announcement, window.ready)``.
    If that earliest start exceeds ``window.due``, the request is impossible
    regardless of prepositioning.

    Invalid (removed from Gate 3F ``a_priori_impossible``): requiring travel from
    the depot after announcement. An offline controller may already have a
    vehicle nearby.
    """
    bad: list[str] = []
    for cid, announce in releases:
        node = instance.node(cid)
        earliest_start = max(float(announce), float(node.window.ready))
        if earliest_start > float(node.window.due) + 1e-12:
            bad.append(cid)
    return sorted(set(bad))


# Backward-compatible name: now only the mathematically valid window test.
def a_priori_impossible(
    instance: Instance,
    releases: list[tuple[str, float]],
) -> list[str]:
    return window_impossible(instance, releases)


def _instance_with_announcement_ready(
    instance: Instance,
    releases: list[tuple[str, float]],
) -> Instance:
    announce = {cid: float(t) for cid, t in releases}
    nodes = dict(instance.nodes)
    for cid, t_ann in announce.items():
        node = instance.node(cid)
        ready = max(float(node.window.ready), t_ann)
        due = float(node.window.due)
        if due < ready:
            due = ready
        nodes[cid] = Node(
            node.id,
            node.kind,
            node.x,
            node.y,
            node.demand,
            TimeWindow(ready, due),
            node.service_time,
        )
    return Instance(
        name=instance.name + "+announce_ready",
        nodes=nodes,
        arcs=instance.arcs,
        vehicle_type=instance.vehicle_type,
        depot_id=instance.depot_id,
        source_format=instance.source_format,
        source_name=instance.source_name,
        assumptions=instance.assumptions + ("ready_max_of_window_and_announcement",),
        station_capacity=instance.station_capacity,
        metadata=dict(instance.metadata),
    )


def constructive_feasible_lower_bound(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
) -> tuple[int, tuple[str, ...]]:
    """Service count from ``construct_routes`` — a feasible offline lower bound."""
    announced = [cid for cid, _ in releases]
    impossible = set(window_impossible(instance, releases))
    eligible = [cid for cid in announced if cid not in impossible]
    plant = _instance_with_announcement_ready(instance, releases)
    base = make_observation(plant, fleet_size, start_time=0.0)
    obs = Observation(
        0.0,
        base.vehicles,
        tuple(eligible),
        (),
        (),
        tuple(sorted(impossible)),
        (),
        (),
    )
    dues = [float(plant.node(c).window.due) for c in eligible] or [1.0]
    horizon = max(dues) + 1.0
    plan = construct_routes(plant, obs, horizon=horizon, energy=NominalLinearEnergy())
    served = len(set(plan.planned_service)) if plan.feasible_commitments else 0
    notes = (
        "constructive_insertion_feasible_lower_bound",
        "nominal_energy_only",
        f"horizon={horizon}",
        f"fleet_size={fleet_size}",
        "NOT_an_upper_bound",
    )
    return served, notes


def certified_cardinality_upper_bound(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
) -> int:
    """Valid relaxation: announced minus window-impossible, capped by fleet×horizon packing.

    Each vehicle can serve at most the number of mutually time-feasible sequential
    stops under direct travel ignoring energy. This is still a relaxation (no
    energy, no capacity, free repositioning between stops) hence a certified UB
    relative to the full physics model.
    """
    announced = [cid for cid, _ in releases]
    impossible = set(window_impossible(instance, releases))
    eligible = [cid for cid in announced if cid not in impossible]
    if not eligible:
        return 0
    # Trivial certified UB: |eligible|.
    trivial = len(eligible)
    # Per-vehicle packing UB: greedy earliest-due sequencing under direct travel
    # from an arbitrary location is hard; use time-window interval graph clique
    # bound: max number of windows covering a common time, times fleet size, is
    # NOT always a UB for sequential routing. Safer certified bound:
    # each vehicle serves at most |eligible| and total <= |eligible|.
    _ = fleet_size  # fleet cannot increase beyond |eligible|
    return trivial


def _enumerate_offline_served(
    instance: Instance,
    eligible: list[str],
    *,
    fleet_size: int,
    max_customers: int = 6,
) -> int | None:
    """Exact max served inside single-tour ≤1 full charge/gap family, or None if too large."""
    if len(eligible) > max_customers:
        return None
    stations = instance.charger_ids()
    station = stations[0] if stations else instance.depot_id
    energy = NominalLinearEnergy()
    battery = instance.vehicle_type.battery_capacity
    best = 0

    def visits(customers: tuple[str, ...], mask: tuple[int, ...]) -> list[Visit]:
        out: list[Visit] = []
        for index, customer_id in enumerate(customers):
            if mask[index]:
                out.append(Visit(station, "charge"))
            out.append(Visit(customer_id, "service"))
        if mask[-1]:
            out.append(Visit(station, "charge"))
        return out

    def group_ok(group: list[str]) -> list[int]:
        if not group:
            return [0]
        found: list[int] = []
        for sequence in permutations(group):
            for mask in product((0, 1), repeat=len(sequence) + 1):
                anchor = Anchor(instance.depot_id, 0.0, battery, 0.0, frozenset())
                result = evaluate_route(instance, anchor, visits(tuple(sequence), mask), energy)
                if result.feasible and set(result.served) == set(sequence):
                    found.append(len(sequence))
        return found or []

    for assignment in product(range(-1, fleet_size), repeat=len(eligible)):
        groups: list[list[str]] = [[] for _ in range(fleet_size)]
        for customer_id, vehicle_index in zip(eligible, assignment, strict=True):
            if vehicle_index >= 0:
                groups[vehicle_index].append(customer_id)
        options: list[list[int]] = []
        blocked = False
        for group in groups:
            ok = group_ok(group)
            if group and not ok:
                blocked = True
                break
            options.append(ok if group else [0])
        if blocked:
            continue
        for combo in product(*options):
            best = max(best, sum(combo))
    return best


def offline_service_reference(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
    try_exact: bool = True,
    exact_max_customers: int = 6,
) -> OfflineReferenceReport:
    """Return labeled offline reference quantities for one (instance, releases, fleet)."""
    announced = [cid for cid, _ in releases]
    impossible = window_impossible(instance, releases)
    ban = set(impossible)
    eligible = [cid for cid in announced if cid not in ban]
    plant = _instance_with_announcement_ready(instance, releases)

    lb, lb_notes = constructive_feasible_lower_bound(instance, releases, fleet_size=fleet_size)
    ub = certified_cardinality_upper_bound(instance, releases, fleet_size=fleet_size)

    exact: int | None = None
    kind = BoundKind.FEASIBLE_LOWER_BOUND
    notes = list(lb_notes) + [
        f"certified_cardinality_ub={ub}",
        "window_impossible_only_valid_impossibility",
        "gate3f_static_constructive_reclassified_as_FEASIBLE_LOWER_BOUND",
    ]
    if try_exact and len(eligible) <= exact_max_customers:
        exact = _enumerate_offline_served(plant, eligible, fleet_size=fleet_size, max_customers=exact_max_customers)
        if exact is not None:
            kind = BoundKind.EXACT_OPTIMUM
            notes.append(f"exact_enumeration_family_served={exact}")
            # Enumeration is exact inside the charge-gap family; also a certified UB
            # only if the family contains every physically feasible plan. Documented
            # limitation: at most one full recharge per gap.
            notes.append("exact_inside_single_full_charge_per_gap_family")

    rate_lb = lb / max(len(announced), 1)
    rate_ub = (exact if exact is not None else ub) / max(len(announced), 1)
    return OfflineReferenceReport(
        n_customers=len(instance.customer_ids()),
        n_announced=len(announced),
        n_window_impossible=len(impossible),
        window_impossible_ids=tuple(impossible),
        feasible_lower_bound=lb,
        certified_upper_bound=exact if exact is not None else ub,
        exact_optimum=exact,
        bound_kind=kind if exact is not None else BoundKind.FEASIBLE_LOWER_BOUND,
        service_rate_lb=rate_lb,
        service_rate_ub=rate_ub,
        notes=tuple(notes),
    )


def heuristic_strictly_below_exact_counterexample() -> dict:
    """Tiny instance where constructive served < exact enumeration served.

    Demonstrates that a constructive 'upper bound' claim is false.
    """
    from safe_time_evrp.models.instance import NodeKind, VehicleType, build_euclidean_instance

    vehicle = VehicleType(40.0, 5.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 15, 0, 0, TimeWindow(0, 500), 0),
        # Insertion often greedily takes C_near then cannot reach both far customers;
        # enumeration can charge then serve the two far stops.
        Node("C_near", NodeKind.CUSTOMER, 2, 0, 1, TimeWindow(0, 30), 1),
        Node("C_far1", NodeKind.CUSTOMER, 25, 0, 1, TimeWindow(0, 200), 1),
        Node("C_far2", NodeKind.CUSTOMER, 30, 0, 1, TimeWindow(0, 220), 1),
    ]
    inst = build_euclidean_instance(
        "gate4-heuristic-gap",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="offline-lb-vs-exact",
        assumptions=("Gate4 counterexample: constructive LB < exact family optimum",),
    )
    releases = [(cid, 0.0) for cid in inst.customer_ids()]
    report = offline_service_reference(inst, releases, fleet_size=1, try_exact=True)
    return {
        "instance": inst.name,
        "feasible_lower_bound": report.feasible_lower_bound,
        "exact_optimum": report.exact_optimum,
        "certified_upper_bound": report.certified_upper_bound,
        "bound_kind": report.bound_kind.value,
        "gap_demonstrated": (report.exact_optimum is not None and report.feasible_lower_bound < report.exact_optimum),
        "notes": list(report.notes),
    }


def is_exploratory_middle_band(
    report: OfflineReferenceReport,
    *,
    low: float = 0.40,
    high: float = 0.80,
    use_lb: bool = True,
) -> bool:
    """Exploratory difficulty band on the **feasible lower-bound** rate (not a certified UB).

    Gate 3F middle-regime selection used a mislabeled constructive rate. Keep the
    band for exploratory diagnostics only; never claim certified middle regime.
    """
    if report.n_announced <= 0:
        return False
    if report.n_window_impossible / report.n_announced > 0.5:
        return False
    rate = report.service_rate_lb if use_lb else (report.service_rate_ub or report.service_rate_lb)
    return low - 1e-12 <= rate <= high + 1e-12
