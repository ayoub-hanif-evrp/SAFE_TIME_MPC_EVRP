"""Generic small dynamic EVRP instance factories (1–2 EVs, 3–5 customers)."""

from __future__ import annotations

from safe_time_evrp.dr_dual.network import ChargerSpec, CustomerSpec, RoadNetwork, Segment
from safe_time_evrp.dr_dual.state import VehicleState, WorldState
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def make_tiny_generic_instance(*, n_customers: int = 3, n_vehicles: int = 1, seed: int = 0) -> RoadNetwork:
    """Structurally generic corridor graph — customer IDs cust_0.. not A/C/S-hardcoded.

    Layout: depot D, customer nodes C0.., charger H0, optional second vehicle from D2.
    """
    del seed  # deterministic layout; seed reserved for generators
    n_customers = max(2, min(5, n_customers))
    n_vehicles = max(1, min(2, n_vehicles))
    nodes = ["D"] + [f"N{i}" for i in range(n_customers)] + ["H0"]
    if n_vehicles == 2:
        nodes.append("D2")
    segs: list[Segment] = []
    # From depot: exploit / inform / mid corridors to first customer
    segs.append(Segment("D_N0_exploit", "D", "N0", 8.0, 3.0, 0.0))
    segs.append(Segment("D_N0_inform", "D", "N0", 10.0, 2.5, 3.0))
    segs.append(Segment("D_N0_slow", "D", "N0", 14.0, 3.0, 2.0))
    # Chain customers
    for i in range(n_customers - 1):
        segs.append(
            Segment(f"N{i}_N{i + 1}", f"N{i}", f"N{i + 1}", 5.0 + 0.5 * i, 2.0 + 0.3 * i, 1.0 if i == 0 else 0.0)
        )
    # Charger access from N0
    segs.append(Segment("N0_H0", "N0", "H0", 1.5, 0.4, 0.0))
    segs.append(Segment("H0_N0", "H0", "N0", 1.5, 0.4, 0.0))
    # Depot returns
    for i in range(n_customers):
        segs.append(Segment(f"N{i}_D", f"N{i}", "D", 6.0, 2.0, 0.0))
    customers = []
    for i in range(n_customers):
        due = 40.0 + 10.0 * i
        ready = 0.0 if i == 0 else 5.0 * i
        reward = 10.0 if i == 0 else 4.0 + i
        customers.append(CustomerSpec(f"cust_{i}", f"N{i}", ready, due, 1.0, reward, demand=1.0))
    meta = {
        "accepted_init": ("cust_0",),
        "announce_at": {f"cust_{i}": float(2 * i) for i in range(n_customers)},
        "require_depot_return": True,
        "vehicles": ("v1",) if n_vehicles == 1 else ("v1", "v2"),
        "start_nodes": {"v1": "D"} if n_vehicles == 1 else {"v1": "D", "v2": "D2"},
        "optional": tuple(f"cust_{i}" for i in range(1, n_customers)),
        "generic": True,
    }
    if n_vehicles == 2:
        segs.append(Segment("D2_N1", "D2", "N1", 9.0, 4.0, 2.0))
        segs.append(Segment("D2_H0", "D2", "H0", 3.0, 1.0, 0.0))
        segs.append(Segment("N1_D2", "N1", "D2", 6.0, 2.0, 0.0))
    return RoadNetwork(
        name=f"generic_n{n_customers}_v{n_vehicles}",
        nodes=tuple(nodes),
        depot="D",
        battery=14.0 if n_customers <= 3 else 18.0,
        segments=tuple(segs),
        customers=tuple(customers),
        chargers=(ChargerSpec("chg_H0", "H0", 6.0),),
        energy_cost=0.05,
        metadata=meta,
    )


def make_no_charger_informative() -> RoadNetwork:
    """Valid network without chargers — informative corridor can still be best."""
    segs = (
        Segment("DA_exploit", "D", "A", 10.0, 4.0, 0.0),
        Segment("DA_inform", "D", "A", 11.0, 3.0, 3.0),
        Segment("AC", "A", "C", 6.0, 5.0, 4.0),  # needs learning for θ=0 direct
        Segment("CD", "C", "D", 4.0, 1.5, 0.0),
    )
    return RoadNetwork(
        name="no_charger_inform",
        nodes=("D", "A", "C"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A", "A", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_C", "C", 0.0, 30.0, 1.0, 5.0),
        ),
        chargers=(),
        energy_cost=0.05,
        metadata={"accepted_init": ("cust_A",), "optional": ("cust_C",), "require_depot_return": False},
    )


def initial_generic_state(net: RoadNetwork) -> WorldState:
    vids = net.metadata.get("vehicles", ("v1",))
    starts = net.metadata.get("start_nodes", {vids[0]: net.depot})
    # Only announce customers with announce_at <= 0 initially
    announce_at = net.metadata.get("announce_at", {})
    announced = frozenset(cid for cid, t in announce_at.items() if float(t) <= 1e-12) | frozenset(
        net.metadata.get("accepted_init", ())
    )
    # Always announce accepted
    accepted = frozenset(net.metadata.get("accepted_init", ()))
    announced = announced | accepted
    vehicles = tuple(VehicleState(vid, starts[vid], 0.0, net.battery) for vid in vids)
    return WorldState(
        vehicles=vehicles,
        accepted=accepted,
        completed=frozenset(),
        rejected=frozenset(),
        announced=announced,
        belief=DiscreteBelief.uniform(net.theta_support),
    )
