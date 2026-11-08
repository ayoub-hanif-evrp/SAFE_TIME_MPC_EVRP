"""Frozen development suite for matched insertion vs ALNS–MPC comparisons."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.phase_b_demo import make_phase_b_instance, phase_b_releases
from safe_time_evrp.models.instance import Instance, Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.optimization.exact_toy import make_reference_instance


@dataclass(frozen=True)
class BaselineCase:
    case_id: str
    instance: Instance
    releases: list[tuple[str, float]]
    fleet_size: int
    horizon: float
    max_replan_interval: float
    t_max: float
    tags: tuple[str, ...]


def _tight_battery() -> Instance:
    vehicle = VehicleType(24.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 6, 0, 0, TimeWindow(0, 500), 0),
        Node("C1", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 180), 2),
        Node("C2", NodeKind.CUSTOMER, 18, 0, 1, TimeWindow(0, 260), 2),
        Node("C3", NodeKind.CUSTOMER, 0, 10, 1, TimeWindow(40, 300), 2),
    ]
    return build_euclidean_instance(
        "baseline_tight_battery",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="baseline-suite",
        assumptions=("synthetic_euclidean", "tight_battery_may_require_charge"),
        metadata={"suite": "baseline_b0"},
    )


def _competing_assign() -> Instance:
    vehicle = VehicleType(50.0, 20.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 400), 0),
        Node("S", NodeKind.CHARGER, 5, 5, 0, TimeWindow(0, 400), 0),
        Node("C1", NodeKind.CUSTOMER, 12, 0, 1, TimeWindow(0, 120), 2),
        Node("C2", NodeKind.CUSTOMER, 0, 12, 1, TimeWindow(0, 120), 2),
        Node("C3", NodeKind.CUSTOMER, 12, 12, 1, TimeWindow(30, 200), 2),
        Node("C4", NodeKind.CUSTOMER, -8, 8, 1, TimeWindow(50, 250), 2),
    ]
    return build_euclidean_instance(
        "baseline_competing",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="baseline-suite",
        assumptions=("synthetic_euclidean", "competing_two_vehicle_assignments"),
        metadata={"suite": "baseline_b0"},
    )


def build_baseline_suite() -> list[BaselineCase]:
    easy = make_reference_instance("easy")
    phase_b = make_phase_b_instance()
    tight = _tight_battery()
    compete = _competing_assign()
    return [
        BaselineCase(
            "B_phase_b",
            phase_b,
            phase_b_releases(),
            2,
            400.0,
            25.0,
            500.0,
            ("phase_b", "charge", "dynamic"),
        ),
        BaselineCase(
            "B_easy_dynamic",
            easy,
            [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)],
            2,
            200.0,
            40.0,
            200.0,
            ("toy", "dynamic"),
        ),
        BaselineCase(
            "B_tight_battery",
            tight,
            [("C1", 0.0), ("C2", 0.0), ("C3", 40.0)],
            2,
            350.0,
            30.0,
            450.0,
            ("tight_battery", "dynamic"),
        ),
        BaselineCase(
            "B_competing",
            compete,
            [("C1", 0.0), ("C2", 0.0), ("C3", 30.0), ("C4", 50.0)],
            2,
            300.0,
            35.0,
            400.0,
            ("competing", "dynamic"),
        ),
    ]
