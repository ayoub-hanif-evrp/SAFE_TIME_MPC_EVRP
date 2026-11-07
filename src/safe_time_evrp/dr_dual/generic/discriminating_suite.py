"""Independently validated development instances with behavioral diversity."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.network import ChargerSpec, CustomerSpec, RoadNetwork, Segment


@dataclass(frozen=True)
class DiscInstance:
    instance_id: str
    net: RoadNetwork
    tags: tuple[str, ...]
    expected_traits: tuple[str, ...]


def _base_meta(**kw):
    m = {
        "require_depot_return": True,
        "generic": True,
        "vehicles": ("v1",),
        "start_nodes": {"v1": "D"},
    }
    m.update(kw)
    return m


def make_multi_customer_accept() -> RoadNetwork:
    """Must serve cust_0 and later-announced cust_1; accept without being at N1 first."""
    segs = (
        Segment("D_N0_exploit", "D", "N0", 8.0, 3.0, 0.0),
        Segment("D_N0_inform", "D", "N0", 10.0, 2.5, 3.0),
        Segment("N0_N1", "N0", "N1", 5.0, 2.0, 1.0),
        Segment("N1_D", "N1", "D", 6.0, 2.0, 0.0),
        Segment("N0_D", "N0", "D", 6.0, 2.0, 0.0),
        Segment("N0_H0", "N0", "H0", 1.5, 0.4, 0.0),
        Segment("H0_N0", "H0", "N0", 1.5, 0.4, 0.0),
    )
    return RoadNetwork(
        name="disc_multi_customer",
        nodes=("D", "N0", "N1", "H0"),
        depot="D",
        battery=14.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_0", "N0", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_1", "N1", 0.0, 50.0, 1.0, 5.0),
        ),
        chargers=(ChargerSpec("chg_H0", "H0", 5.0),),
        energy_cost=0.05,
        metadata=_base_meta(
            accepted_init=("cust_0",),
            announce_at={"cust_0": 0.0, "cust_1": 2.0},
            optional=("cust_1",),
        ),
    )


def make_two_ev_split() -> RoadNetwork:
    """EV2 serves cust_1 from D2 while EV1 serves cust_0."""
    segs = (
        Segment("D_N0_exploit", "D", "N0", 8.0, 3.0, 0.0),
        Segment("D_N0_inform", "D", "N0", 12.0, 2.0, 4.0),
        Segment("N0_D", "N0", "D", 6.0, 2.0, 0.0),
        Segment("D2_N1", "D2", "N1", 7.0, 3.0, 2.0),
        Segment("N1_D2", "N1", "D2", 6.0, 2.0, 0.0),
        Segment("D2_H0", "D2", "H0", 2.0, 1.0, 0.0),
        Segment("H0_D2", "H0", "D2", 2.0, 1.0, 0.0),
    )
    return RoadNetwork(
        name="disc_two_ev",
        nodes=("D", "N0", "D2", "N1", "H0"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_0", "N0", 0.0, 80.0, 1.0, 10.0),
            CustomerSpec("cust_1", "N1", 0.0, 40.0, 1.0, 8.0),
        ),
        chargers=(ChargerSpec("chg_H0", "H0", 4.0),),
        energy_cost=0.05,
        metadata=_base_meta(
            accepted_init=("cust_0", "cust_1"),
            announce_at={"cust_0": 0.0, "cust_1": 0.0},
            vehicles=("v1", "v2"),
            start_nodes={"v1": "D", "v2": "D2"},
            optional=(),
        ),
    )


def make_charge_required() -> RoadNetwork:
    """Tight battery: must charge before optional cust_1."""
    segs = (
        Segment("D_N0_exploit", "D", "N0", 6.0, 5.0, 0.0),
        Segment("D_N0_inform", "D", "N0", 8.0, 4.0, 3.0),
        Segment("N0_N1", "N0", "N1", 5.0, 6.0, 2.0),  # needs charge after first leg
        Segment("N0_H0", "N0", "H0", 1.0, 0.5, 0.0),
        Segment("H0_N0", "H0", "N0", 1.0, 0.5, 0.0),
        Segment("N1_D", "N1", "D", 5.0, 2.0, 0.0),
        Segment("N0_D", "N0", "D", 5.0, 2.0, 0.0),
    )
    return RoadNetwork(
        name="disc_charge_required",
        nodes=("D", "N0", "N1", "H0"),
        depot="D",
        battery=10.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_0", "N0", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_1", "N1", 0.0, 60.0, 1.0, 7.0),
        ),
        chargers=(ChargerSpec("chg_H0", "H0", 3.0),),
        energy_cost=0.05,
        metadata=_base_meta(
            accepted_init=("cust_0",),
            announce_at={"cust_0": 0.0, "cust_1": 0.0},
            optional=("cust_1",),
        ),
    )


def make_info_changes_action() -> RoadNetwork:
    """Informative first corridor changes whether optional C is taken (energy)."""
    segs = (
        Segment("D_N0_exploit", "D", "N0", 8.0, 4.0, 0.0),
        Segment("D_N0_inform", "D", "N0", 10.0, 3.0, 4.0),
        Segment("N0_N1", "N0", "N1", 6.0, 5.0, 4.0),  # 5 vs 9
        Segment("N1_D", "N1", "D", 5.0, 2.0, 0.0),
        Segment("N0_D", "N0", "D", 5.0, 2.0, 0.0),
        Segment("N0_H0", "N0", "H0", 1.0, 0.5, 0.0),
        Segment("H0_N0", "H0", "N0", 1.0, 0.5, 0.0),
    )
    return RoadNetwork(
        name="disc_info_value",
        nodes=("D", "N0", "N1", "H0"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_0", "N0", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_1", "N1", 0.0, 35.0, 1.0, 6.0),
        ),
        chargers=(ChargerSpec("chg_H0", "H0", 8.0),),
        energy_cost=0.05,
        metadata=_base_meta(
            accepted_init=("cust_0",),
            announce_at={"cust_0": 0.0, "cust_1": 0.0},
            optional=("cust_1",),
        ),
    )


def build_discriminating_suite() -> list[DiscInstance]:
    return [
        DiscInstance("D1_multi_accept", make_multi_customer_accept(), ("multi_customer",), ("serve_two", "accept_after_announce")),
        DiscInstance("D2_two_ev", make_two_ev_split(), ("two_ev",), ("both_vehicles",)),
        DiscInstance("D3_charge", make_charge_required(), ("charge",), ("necessary_charge",)),
        DiscInstance("D4_info", make_info_changes_action(), ("info",), ("observation_changes_action",)),
    ]
