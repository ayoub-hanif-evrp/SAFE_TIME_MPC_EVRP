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


def _adversarial_overaccept() -> Instance:
    """Tight windows: accepting an extra late customer can break an early commitment."""
    vehicle = VehicleType(40.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        Node("S", NodeKind.CHARGER, 4, 0, 0, TimeWindow(0, 300), 0),
        Node("C1", NodeKind.CUSTOMER, 8, 0, 1, TimeWindow(0, 40), 2),
        Node("C2", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 55), 2),
        Node("C3", NodeKind.CUSTOMER, 0, 15, 1, TimeWindow(0, 200), 2),
    ]
    return build_euclidean_instance(
        "baseline_adversarial_overaccept",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="baseline-suite",
        assumptions=("synthetic_euclidean", "extra_accept_may_break_commitment"),
        metadata={"suite": "baseline_b0", "adversarial": "1"},
    )


def _grid_customers(n: int, *, seed_name: str, span: float = 40.0) -> Instance:
    """Diverse Euclidean grid with a charger; battery tight enough to force some charging."""
    vehicle = VehicleType(35.0, 30.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 2000), 0),
        Node("S", NodeKind.CHARGER, span * 0.25, span * 0.25, 0, TimeWindow(0, 2000), 0),
    ]
    # Spread customers in a ring/grid mix for geometric diversity.
    cols = max(3, int(n**0.5) + 1)
    for i in range(n):
        x = ((i % cols) + 1) * (span / (cols + 1))
        y = ((i // cols) + 1) * (span / (cols + 1))
        if i % 3 == 0:
            x, y = y, -x * 0.5
        due = 200 + 40 * i
        nodes.append(Node(f"C{i + 1}", NodeKind.CUSTOMER, x, y, 1, TimeWindow(0, due), 2))
    return build_euclidean_instance(
        seed_name,
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="baseline-scaled",
        assumptions=("synthetic_euclidean", "scaled_dynamic_development"),
        metadata={"suite": "scaled"},
    )


def _scaled_releases(n: int) -> list[tuple[str, float]]:
    releases: list[tuple[str, float]] = []
    for i in range(n):
        # Stagger arrivals: first third at 0, rest dynamically.
        t = 0.0 if i < max(3, n // 3) else 15.0 * (i - n // 3 + 1)
        releases.append((f"C{i + 1}", t))
    return releases


def _rescue_pack_case() -> BaselineCase:
    vehicle = VehicleType(500.0, 2.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 5000), 0),
        Node("S", NodeKind.CHARGER, 0, 1, 0, TimeWindow(0, 5000), 0),
        Node("A", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 40), 1),
        Node("B", NodeKind.CUSTOMER, 0, 5, 1, TimeWindow(0, 45), 1),
        Node("C", NodeKind.CUSTOMER, 50, 0, 2, TimeWindow(0, 55), 1),
    ]
    pack = build_euclidean_instance(
        "baseline_rescue_pack",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="baseline-scaled",
        assumptions=("request_rescue_fixture",),
        metadata={"suite": "scaled", "adversarial": "1"},
    )
    return BaselineCase(
        "B_rescue_pack",
        pack,
        [("A", 0.0), ("B", 0.0), ("C", 0.0)],
        2,
        400.0,
        50.0,
        400.0,
        ("rescue", "constructor_miss"),
    )


def build_scaled_suite() -> list[BaselineCase]:
    """10–30 customer multi-vehicle dynamic development cases."""
    cases: list[BaselineCase] = []
    for n, fleet, tag in ((12, 2, "scaled_12"), (20, 3, "scaled_20"), (28, 3, "scaled_28")):
        inst = _grid_customers(n, seed_name=f"baseline_{tag}", span=30.0 + n)
        cases.append(
            BaselineCase(
                f"B_{tag}",
                inst,
                _scaled_releases(n),
                fleet,
                500.0,
                40.0,
                900.0,
                ("scaled", "dynamic", "multi_vehicle", tag),
            )
        )
    cases.append(_rescue_pack_case())
    return cases


def build_frontier_suite() -> list[BaselineCase]:
    """Priority-7 development frontier: 10/20/30/50 customers, multi-EV, dynamic, tight SOC."""
    cases: list[BaselineCase] = []
    specs = (
        (10, 2, "frontier_10", 28.0, 28.0),
        (20, 3, "frontier_20", 32.0, 30.0),
        (30, 3, "frontier_30", 34.0, 32.0),
        (50, 4, "frontier_50", 36.0, 34.0),
    )
    for n, fleet, tag, battery, span in specs:
        vehicle = VehicleType(battery, 40.0, 1.0, 0.5, 1.0, "full")
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 3000), 0),
            Node("S", NodeKind.CHARGER, span * 0.2, span * 0.2, 0, TimeWindow(0, 3000), 0),
            Node("S2", NodeKind.CHARGER, -span * 0.15, span * 0.3, 0, TimeWindow(0, 3000), 0),
        ]
        cols = max(3, int(n**0.5) + 1)
        for i in range(n):
            x = ((i % cols) + 1) * (span / (cols + 1))
            y = ((i // cols) + 1) * (span / (cols + 1))
            if i % 4 == 0:
                x, y = -y * 0.7, x * 0.6
            elif i % 4 == 1:
                x, y = x * 1.1, -y * 0.5
            due = 120 + 25 * i
            nodes.append(Node(f"C{i + 1}", NodeKind.CUSTOMER, x, y, 1, TimeWindow(0, due), 2))
        inst = build_euclidean_instance(
            f"baseline_{tag}",
            nodes,
            vehicle,
            source_format="synthetic",
            source_name="frontier-suite",
            assumptions=("synthetic_euclidean", "frontier_tight_soc", "dynamic_releases"),
            metadata={"suite": "frontier"},
        )
        cases.append(
            BaselineCase(
                f"B_{tag}",
                inst,
                _scaled_releases(n),
                fleet,
                600.0,
                35.0,
                1200.0 if n < 50 else 1600.0,
                ("frontier", "dynamic", "multi_vehicle", "tight_soc", tag),
            )
        )
    cases.append(_rescue_pack_case())
    return cases


def build_baseline_suite() -> list[BaselineCase]:
    easy = make_reference_instance("easy")
    phase_b = make_phase_b_instance()
    tight = _tight_battery()
    compete = _competing_assign()
    adv = _adversarial_overaccept()
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
        BaselineCase(
            "B_adversarial_overaccept",
            adv,
            [("C1", 0.0), ("C2", 0.0), ("C3", 0.0)],
            1,
            200.0,
            40.0,
            300.0,
            ("adversarial", "commitment_vs_new_accept"),
        ),
    ]
