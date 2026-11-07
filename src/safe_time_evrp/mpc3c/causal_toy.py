"""Hand-crafted microscopic instance for present-action divergence."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.testbed.constructor import make_observation


def energy_fork_instance():
    """Close customer vs charge-preserving path under tight battery."""
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 40), 1),
        Node("B", NodeKind.CUSTOMER, 0, 8, 1, TimeWindow(0, 50), 1),
        Node("S", NodeKind.CHARGER, 0, 4, 0, TimeWindow(0, 100), 0),
    ]
    vehicle = VehicleType(
        battery_capacity=12.0,
        load_capacity=10.0,
        consumption_rate=1.0,
        inverse_recharge_rate=0.2,
        velocity=1.0,
        recharge_policy="full",
    )
    return build_euclidean_instance(
        "causal_energy_fork",
        nodes,
        vehicle,
        source_format="gate3c_toy",
        source_name="flexibility_microscope",
        assumptions=("euclidean_toy_for_causal_mechanism",),
    )


def present_actions(instance=None, fleet_size: int = 1, horizon: float = 30.0) -> dict:
    inst = instance or energy_fork_instance()
    obs = make_observation(inst, fleet_size)
    out = {}
    for kind in ControllerKind:
        decision = decide(inst, obs, kind, horizon=horizon)
        out[kind.value] = {
            vid: (None if a is None else (a.node_id, a.purpose)) for vid, a in decision.first_actions.items()
        }
    return out
