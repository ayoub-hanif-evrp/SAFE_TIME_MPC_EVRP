"""Gate 3B pilot and oracle-correction tests."""

from __future__ import annotations

import math
from pathlib import Path

from safe_time_evrp.data.evrp_tw_d import (
    extract_root,
    list_solomon_files,
    parse_solomon_file,
    with_battery_fraction,
)
from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType
from safe_time_evrp.multistage.oracle import Status, open_loop_feasible
from safe_time_evrp.multistage.toys import routing_fork_commitment
from safe_time_evrp.pilot.feasibility import pilot_contrast, replay_route


def _toy_road_instance(battery: float = 10.0, rate: float = 1.0) -> Instance:
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        Node("C1", NodeKind.CUSTOMER, 1, 0, 1, TimeWindow(0, 100), 0),
        Node("C2", NodeKind.CUSTOMER, 2, 0, 1, TimeWindow(0, 100), 0),
        Node("S", NodeKind.CHARGER, 1.5, 1, 0, TimeWindow(0, 100), 0),
    ]
    matrix = {
        ("D", "C1"): 3.0,
        ("C1", "D"): 3.2,
        ("D", "C2"): 6.0,
        ("C2", "D"): 6.1,
        ("D", "S"): 4.0,
        ("S", "D"): 4.0,
        ("C1", "C2"): 3.0,
        ("C2", "C1"): 3.1,
        ("C1", "S"): 1.0,
        ("S", "C1"): 1.0,
        ("C2", "S"): 2.0,
        ("S", "C2"): 2.0,
    }
    vehicle = VehicleType(battery, 100, rate, 0.1, 40.0, "partial")
    arcs = {
        (o, d): Arc(o, d, dist, dist / 40.0, rate * dist, "road_network_source", distance_km=dist)
        for (o, d), dist in matrix.items()
    }
    return Instance(
        name="toy_road_pilot",
        nodes={n.id: n for n in nodes},
        arcs=arcs,
        vehicle_type=vehicle,
        depot_id="D",
        source_format="synthetic_road",
        source_name="gate3b_toy",
        metadata={"vehicle_config": "toy"},
    )


def test_road_instance_asymmetric_not_euclidean_hypot():
    inst = _toy_road_instance()
    assert inst.arcs[("D", "C1")].distance != inst.arcs[("C1", "D")].distance
    # Explicit: stored road distance is 3.0, coordinate hypot would be 1.0.
    assert inst.arcs[("D", "C1")].distance == 3.0
    assert math.hypot(0 - 1, 0 - 0) == 1.0


def test_replay_detects_energy_shortfall_and_charge_rescue():
    inst = _toy_road_instance(battery=10.0, rate=1.0)
    report = pilot_contrast(inst)
    assert report["nn_feasible_without_charge"] is False
    assert report["nn_plus_charge_feasible"] is True
    assert report["battery_changes_decision"] is True


def test_open_loop_exhaustion_still_infeasible_not_time_limit():
    assert open_loop_feasible(routing_fork_commitment()) is Status.PROVEN_INFEASIBLE


def test_independent_replay_on_feasible_short_route():
    inst = _toy_road_instance(battery=50.0, rate=0.1)
    assert replay_route(inst, ["D", "C1", "C2", "D"], charge_to_full_at_chargers=False).feasible


def test_evrp_tw_d_solomon_parser_if_present():
    raw = Path("data/raw/evrp_tw_d")
    try:
        root = extract_root(raw)
        files = list_solomon_files(root, scale="Cus_5")
    except FileNotFoundError:
        return
    inst = parse_solomon_file(files[0])
    assert inst.source_format == "evrp_tw_d_solomon"
    assert all(a.distance_definition == "evrp_tw_d_2norm_source" for a in inst.arcs.values())
    assert len(inst.customers) == 5
    assert len(inst.chargers) >= 1
    small = with_battery_fraction(inst, 0.125, "bat12p5")
    assert small.vehicle_type.battery_capacity < inst.vehicle_type.battery_capacity
