"""Frozen preregistered generic instance generator (seeds fixed before comparisons)."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.generic.model import make_tiny_generic_instance
from safe_time_evrp.dr_dual.network import ChargerSpec, CustomerSpec, RoadNetwork, Segment

# Frozen seed list — do not reorder after first compute study commit.
FROZEN_SEEDS: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)


@dataclass(frozen=True)
class FrozenInstance:
    instance_id: str
    seed: int
    net: RoadNetwork
    tags: tuple[str, ...]


def _mutate(net: RoadNetwork, seed: int) -> RoadNetwork:
    """Structural variation from seed (deterministic)."""
    battery = net.battery + (seed % 3) * 2.0
    charge_t = net.chargers[0].full_charge_time if net.chargers else 6.0
    charge_t = charge_t * (0.7 + 0.1 * (seed % 4))
    customers = []
    for i, c in enumerate(net.customers):
        due = c.due + (seed % 5) * 2.0 - (3 if seed % 2 == 0 and i > 0 else 0)
        customers.append(CustomerSpec(c.customer_id, c.node, c.ready, due, c.service_time, c.reward, c.demand))
    segs = []
    for s in net.segments:
        phi1 = s.informative
        if "inform" in s.segment_id:
            phi1 = 2.0 + (seed % 3)
        segs.append(Segment(s.segment_id, s.origin, s.destination, s.travel_time, s.base_energy, phi1))
    chargers = tuple(ChargerSpec(ch.charger_id, ch.node, charge_t) for ch in net.chargers)
    return RoadNetwork(
        name=f"{net.name}_s{seed}",
        nodes=net.nodes,
        depot=net.depot,
        battery=battery,
        segments=tuple(segs),
        customers=tuple(customers),
        chargers=chargers,
        energy_cost=net.energy_cost,
        theta_support=net.theta_support,
        metadata=dict(net.metadata),
    )


def build_frozen_generic_suite() -> list[FrozenInstance]:
    out: list[FrozenInstance] = []
    configs = [
        (3, 1, ("n3_v1",)),
        (4, 1, ("n4_v1",)),
        (3, 2, ("n3_v2",)),
        (5, 1, ("n5_v1",)),
    ]
    for seed in FROZEN_SEEDS:
        n_c, n_v, tags = configs[seed % len(configs)]
        base = make_tiny_generic_instance(n_customers=n_c, n_vehicles=n_v, seed=seed)
        net = _mutate(base, seed)
        out.append(FrozenInstance(f"G{seed}_{n_c}c_{n_v}v", seed, net, tags + (f"seed{seed}",)))
    return out
