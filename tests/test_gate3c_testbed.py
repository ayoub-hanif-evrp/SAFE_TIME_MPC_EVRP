"""Gate 3C testbed constructor and validator tests."""

from __future__ import annotations

from pathlib import Path

from safe_time_evrp.data.evrp_tw_d import extract_root, list_solomon_files, parse_solomon_file
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.testbed.constructor import construct_feasible_seed, find_minimal_fleet_seed
from safe_time_evrp.testbed.validator import validate_fleet_plan


def test_validator_rejects_empty_routes_when_customers_required():
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        Node("C1", NodeKind.CUSTOMER, 1, 0, 1, TimeWindow(0, 50), 1),
    ]
    vehicle = VehicleType(100, 10, 0.1, 0.1, 1.0, "full")
    inst = build_euclidean_instance(
        "tiny",
        nodes,
        vehicle,
        source_format="test",
        source_name="test",
    )
    report = validate_fleet_plan(inst, {"v0": []}, require_all_customers=True)
    assert report.feasible is False
    assert any("unserved" in r for r in report.reasons)


def test_evrptwd_seed_construction_if_present():
    raw = Path("data/raw/evrp_tw_d")
    try:
        root = extract_root(raw)
        files = [f for f in list_solomon_files(root, scale="Cus_5") if "wide" in f.name][:3]
    except FileNotFoundError:
        return
    if not files:
        return
    ok = 0
    for path in files:
        seed = find_minimal_fleet_seed(parse_solomon_file(path), max_fleet=5)
        if seed.validation.feasible:
            ok += 1
            assert seed.plan is not None
            assert seed.validation.vehicles_used >= 1
    assert ok >= 2


def test_construct_feasible_seed_reports_fleet_size():
    raw = Path("data/raw/evrp_tw_d")
    try:
        root = extract_root(raw)
        path = next(f for f in list_solomon_files(root, scale="Cus_5") if "wide" in f.name)
    except (FileNotFoundError, StopIteration):
        return
    seed = construct_feasible_seed(parse_solomon_file(path), fleet_size=3, recharge_policy="full")
    assert seed.fleet_size == 3
    assert seed.validation.feasible
