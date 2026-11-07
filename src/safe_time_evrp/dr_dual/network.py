"""Road-segment graph with multiple physical corridors (distinct segment IDs)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Segment:
    """One directed physical road segment (not a logical OD abstract arc)."""

    segment_id: str
    origin: str
    destination: str
    travel_time: float
    base_energy: float  # phi_0
    informative: float  # phi_1 coefficient on shared theta
    kind: str = "road"  # road | charge_access


@dataclass(frozen=True)
class CustomerSpec:
    customer_id: str
    node: str
    ready: float
    due: float
    service_time: float
    reward: float
    demand: float = 1.0


@dataclass(frozen=True)
class ChargerSpec:
    charger_id: str
    node: str
    full_charge_time: float  # time to go from 0 to battery (linear)
    # Partial charging: energy delta * (full_charge_time / battery)


@dataclass
class RoadNetwork:
    """Tiny dynamic-EVRP road network with explicit alternative corridors."""

    name: str
    nodes: tuple[str, ...]
    depot: str
    battery: float
    segments: tuple[Segment, ...]
    customers: tuple[CustomerSpec, ...]
    chargers: tuple[ChargerSpec, ...]
    theta_support: tuple[float, ...] = (0.0, 1.0)
    energy_cost: float = 0.05
    metadata: dict = field(default_factory=dict)

    def segments_from(self, node: str) -> list[Segment]:
        return [s for s in self.segments if s.origin == node]

    def customer(self, cid: str) -> CustomerSpec:
        for c in self.customers:
            if c.customer_id == cid:
                return c
        raise KeyError(cid)

    def charger_at(self, node: str) -> ChargerSpec | None:
        for ch in self.chargers:
            if ch.node == node:
                return ch
        return None

    def energy(self, segment: Segment, theta: float) -> float:
        return float(segment.base_energy + segment.informative * theta)


def make_single_ev_corridors() -> RoadNetwork:
    """1 EV, corridors D→A (exploit/inform), charger S, optional C, commitment A."""
    segs = (
        Segment("DA_exploit", "D", "A", travel_time=10.0, base_energy=4.0, informative=0.0),
        Segment("DA_inform", "D", "A", travel_time=12.0, base_energy=3.0, informative=3.0),
        # Informative but arrives too late for optional C → zero decision-relevant VoI.
        Segment("DA_useless_inform", "D", "A", travel_time=22.0, base_energy=3.0, informative=3.0),
        Segment("AS", "A", "S", travel_time=1.0, base_energy=0.5, informative=0.0),
        Segment("SA", "S", "A", travel_time=1.0, base_energy=0.5, informative=0.0),
        # AC energy = 6+4*theta → needs 6 (θ=0) or 10 (θ=1). Post-exploit SOC=8 cannot
        # robustly serve C; post-inform θ=0 SOC=9 still cannot robustly serve C under prior
        # (θ=1 needs 10), but Dirac θ=0 can serve C — VoI appears only after learning.
        Segment("AC", "A", "C", travel_time=8.0, base_energy=6.0, informative=4.0),
        Segment("CD", "C", "D", travel_time=5.0, base_energy=2.0, informative=0.0),
    )
    return RoadNetwork(
        name="dr_single_ev_corridors",
        nodes=("D", "A", "S", "C"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A", "A", ready=0.0, due=100.0, service_time=1.0, reward=10.0),
            # due=24: full charge after A makes C late, so robust post-exploit plans cannot serve C
            CustomerSpec("cust_C", "C", ready=0.0, due=24.0, service_time=1.0, reward=5.0),
        ),
        chargers=(ChargerSpec("chg_S", "S", full_charge_time=15.0),),
        metadata={"accepted_init": ("cust_A",), "optional": ("cust_C",)},
    )


def make_two_ev_shared_theta() -> RoadNetwork:
    """2 EVs: EV1 corridor choice informs EV2 charge/skip for optional B.

    Timing: EV1 finishes A and observes energy before EV2's charge decision epoch.
    Shared theta: high energy makes EV2 need a charge before B; low skips charge.
    """
    segs = (
        # EV1 from D1
        Segment("E1_exploit", "D1", "A1", travel_time=8.0, base_energy=3.0, informative=0.0),
        Segment("E1_inform", "D1", "A1", travel_time=10.0, base_energy=2.0, informative=4.0),
        Segment("A1_S1", "A1", "S1", travel_time=1.0, base_energy=0.4, informative=0.0),
        # EV2 from D2
        Segment("E2_to_B", "D2", "B", travel_time=9.0, base_energy=5.0, informative=3.0),
        Segment("D2_S2", "D2", "S2", travel_time=2.0, base_energy=1.0, informative=0.0),
        Segment("S2_B", "S2", "B", travel_time=7.0, base_energy=4.0, informative=2.0),
    )
    return RoadNetwork(
        name="dr_two_ev_shared_theta",
        nodes=("D1", "A1", "S1", "D2", "S2", "B"),
        depot="D1",  # primary; EV2 starts at D2 via vehicle state
        battery=14.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A1", "A1", ready=0.0, due=80.0, service_time=1.0, reward=10.0),
            CustomerSpec("cust_B", "B", ready=12.0, due=35.0, service_time=1.0, reward=6.0),
        ),
        chargers=(
            ChargerSpec("chg_S1", "S1", full_charge_time=12.0),
            ChargerSpec("chg_S2", "S2", full_charge_time=10.0),
        ),
        metadata={
            "accepted_init": ("cust_A1",),
            "optional": ("cust_B",),
            "vehicles": ("v1", "v2"),
            "start_nodes": {"v1": "D1", "v2": "D2"},
            "v2_decision_after_time": 11.0,  # after EV1 inform/exploit completes
        },
    )
