"""Exhaustive reference for tiny single-tour EVRP instances.

The search enumerates assignments of each customer to a vehicle or to the
unserved set, customer orders, and at most one full recharge in each gap.
Waiting follows the benchmark rule. Optional extra waiting is outside this family.

A result is proven only inside that finite family.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import (
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    VehicleType,
    build_euclidean_instance,
)
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.optimization.insertion import construct_routes


@dataclass(frozen=True)
class ToyCertificate:
    family: str
    best_served: int
    best_distance: float
    best_charge_time: float
    feasible_exists: bool
    heuristic_served: int
    heuristic_distance: float
    heuristic_status: str
    note: str


def make_reference_instance(case: str) -> Instance:
    if case == "easy":
        vehicle = VehicleType(50.0, 10.0, 1.0, 1.0, 1.0, "full")
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
            Node("S", NodeKind.CHARGER, 5, 0, 0, TimeWindow(0, 200), 0),
            Node("C1", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 80), 2),
            Node("C2", NodeKind.CUSTOMER, 0, 10, 1, TimeWindow(0, 80), 2),
            Node("C3", NodeKind.CUSTOMER, 10, 10, 1, TimeWindow(20, 120), 2),
        ]
    elif case == "needs_two_charges":
        vehicle = VehicleType(25.0, 10.0, 1.0, 0.1, 1.0, "full")
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
            Node("S", NodeKind.CHARGER, 10, 0, 0, TimeWindow(0, 500), 0),
            Node("C1", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 400), 1),
        ]
    elif case == "impossible_window":
        vehicle = VehicleType(50.0, 10.0, 1.0, 1.0, 1.0, "full")
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
            Node("S", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
            Node("C1", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 1), 1),
            Node("C2", NodeKind.CUSTOMER, 1, 0, 1, TimeWindow(0, 40), 1),
        ]
    else:
        raise ValueError(f"unknown toy case {case}")
    return build_euclidean_instance(
        f"toy-{case}",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name=f"exact-toy-{case}",
        assumptions=(
            "Coordinates are the metric for this toy.",
            "Enumeration allows at most one full recharge between successive stops.",
        ),
    )


def _observation(instance: Instance, fleet_size: int) -> Observation:
    battery = instance.vehicle_type.battery_capacity
    vehicles = []
    for index in range(fleet_size):
        anchor = Anchor(instance.depot_id, 0.0, battery, 0.0, frozenset())
        vehicles.append(
            VehicleView(
                id=f"v{index + 1}",
                status="idle",
                node=instance.depot_id,
                soc=battery,
                load=0.0,
                onboard=(),
                anchor=anchor,
                locked_destination=None,
            )
        )
    customers = tuple(instance.customer_ids())
    return Observation(0.0, tuple(vehicles), customers, (), (), (), (), ())


def _visits(customers: tuple[str, ...], station: str, mask: tuple[int, ...]) -> list[Visit]:
    visits: list[Visit] = []
    for index, customer_id in enumerate(customers):
        if mask[index]:
            visits.append(Visit(station, "charge"))
        visits.append(Visit(customer_id, "service"))
    if mask[-1]:
        visits.append(Visit(station, "charge"))
    return visits


def _feasible_options(
    instance: Instance,
    customers: list[str],
    station: str,
) -> list[tuple[float, float, int]] | None:
    """Feasible (distance, charge time, served count) routes, or None if none exist."""
    energy = NominalLinearEnergy()
    anchor = Anchor(
        instance.depot_id,
        0.0,
        instance.vehicle_type.battery_capacity,
        0.0,
        frozenset(),
    )
    found: list[tuple[float, float, int]] = []
    sequences = permutations(customers) if customers else [()]
    for sequence in sequences:
        for mask in product((0, 1), repeat=len(sequence) + 1):
            result = evaluate_route(instance, anchor, _visits(tuple(sequence), station, mask), energy)
            if result.feasible and set(result.served) == set(sequence):
                found.append((result.distance, result.charge_time, len(sequence)))
    if customers and not found:
        return None
    return found or [(0.0, 0.0, 0)]


def enumerate_case(case: str, fleet_size: int = 2) -> ToyCertificate:
    instance = make_reference_instance(case)
    customers = instance.customer_ids()
    station = instance.charger_ids()[0]
    best_served = 0
    best_distance = 0.0
    best_charge = 0.0
    have_best = False
    for assignment in product(range(-1, fleet_size), repeat=len(customers)):
        groups: list[list[str]] = [[] for _ in range(fleet_size)]
        for customer_id, vehicle_index in zip(customers, assignment, strict=True):
            if vehicle_index >= 0:
                groups[vehicle_index].append(customer_id)
        options = []
        blocked = False
        for group in groups:
            found = _feasible_options(instance, group, station)
            if found is None:
                blocked = True
                break
            options.append(found)
        if blocked:
            continue
        for combo in product(*options):
            served = sum(item[2] for item in combo)
            distance = sum(item[0] for item in combo)
            charge = sum(item[1] for item in combo)
            key = (-served, distance, charge)
            best_key = (-best_served, best_distance, best_charge) if have_best else None
            if best_key is None or key < best_key:
                best_served = served
                best_distance = distance
                best_charge = charge
                have_best = True
    heuristic = construct_routes(
        instance,
        _observation(instance, fleet_size),
        horizon=10_000.0,
    )
    h_served = len(heuristic.planned_service)
    h_distance = heuristic.total_distance
    if h_served == best_served and abs(h_distance - best_distance) <= 1e-6:
        status = "heuristic_matches_proven_optimum"
    elif h_served == best_served:
        status = "heuristic_feasible_service_count_matches"
    elif h_served == 0 and best_served > 0:
        status = "heuristic_missed_a_proven_feasible_route"
    else:
        status = "heuristic_feasible"
    return ToyCertificate(
        family="single_tour_at_most_one_full_charge_per_gap",
        best_served=best_served,
        best_distance=best_distance,
        best_charge_time=best_charge,
        feasible_exists=best_served > 0,
        heuristic_served=h_served,
        heuristic_distance=h_distance,
        heuristic_status=status,
        note=(
            "Proven only inside the enumerated family on this toy. "
            "A heuristic miss does not prove that the customer is infeasible."
        ),
    )


def forced_first_travel(case: str, customer_id: str, destination: str) -> str:
    """Classify a depot departure whose first stop is ``destination``.

    Freight for ``customer_id`` is loaded before that departure. The label is
    proven_feasible when some enumerated continuation still serves that customer,
    and proven_infeasible when none does.
    """
    instance = make_reference_instance(case)
    arc = instance.arc(instance.depot_id, destination)
    battery = instance.vehicle_type.battery_capacity
    if arc.energy > battery + 1e-9:
        return "proven_infeasible"
    demand = instance.node(customer_id).demand
    anchor = Anchor(
        destination,
        arc.travel_time,
        battery - arc.energy,
        demand,
        frozenset({customer_id}),
    )
    remaining = [cid for cid in instance.customer_ids() if cid != customer_id]
    if destination != customer_id:
        remaining = [customer_id, *remaining]
    elif instance.node(customer_id).window.due + 1e-9 < anchor.time:
        return "proven_infeasible"
    station = instance.charger_ids()[0]
    if destination == customer_id:
        # Arrival does not itself serve the customer. Service is the continuation.
        # The customer we traveled to must be served before the rest, while we are there,
        # or later if we leave and return. Try both by putting them in ``remaining`` only
        # when we did not stop on them. Here we did stop, so prepend service.
        prefixed = [(customer_id, *sequence) for sequence in ([()] if not remaining else permutations(remaining))]
        search = [tuple(item) for item in prefixed]
    else:
        search = list(permutations(remaining))
    for sequence in search:
        for mask in product((0, 1), repeat=len(sequence) + 1):
            result = evaluate_route(
                instance,
                anchor,
                _visits(tuple(sequence), station, mask),
                NominalLinearEnergy(),
            )
            if result.feasible and customer_id in result.served:
                return "proven_feasible"
    return "proven_infeasible"
