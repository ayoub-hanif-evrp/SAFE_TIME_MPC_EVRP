"""Hand-crafted microscopic forks for MPC action-causality tests.

These are correctness / causality fixtures, not evidence of general superiority.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Instance, Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView


@dataclass(frozen=True)
class ForkSpec:
    case_id: str
    instance: Instance
    observation: Observation
    scenarios: tuple[tuple[tuple[str, float], ...], ...]
    scenario_probs: tuple[float, ...]
    candidate_actions: tuple[str, ...]
    notes: tuple[str, ...]


def _obs_one_vehicle(inst: Instance, *, soc: float | None = None, released: tuple[str, ...] = ()) -> Observation:
    bat = inst.vehicle_type.battery_capacity if soc is None else soc
    anchor = Anchor(inst.depot_id, 0.0, bat, 0.0, frozenset())
    v = VehicleView("v1", "idle", inst.depot_id, bat, 0.0, (), anchor, None)
    return Observation(0.0, (v,), released, (), (), (), (), ())


def case_a_predictive_charging_fork() -> ForkSpec:
    """Serve Near now vs charge first under possible far future demand.

    Geometry (velocity=1, consumption=1, inverse_recharge=0.5):
      D=(0,0), S=(0,3), Near=(6,0), Far=(0,9); start SOC=16, capacity=40.

    Serving Near first still allows a depot return, but charging afterward makes
    Far miss its due time. Charging first preserves a feasible Near+Far tour.

    Scenarios:
      ω0: Far never appears → reactive optimum serve_near.
      ω1: Far announced at t=1 → stochastic prefers charge_first.
    """
    vehicle = VehicleType(40.0, 5.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 0, 3, 0, TimeWindow(0, 500), 0),
        Node("Near", NodeKind.CUSTOMER, 6, 0, 1, TimeWindow(0, 200), 2),
        Node("Far", NodeKind.CUSTOMER, 0, 9, 1, TimeWindow(0, 40), 1),
    ]
    inst = build_euclidean_instance(
        "mpc_central_case_a_charge_fork",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="mpc_central_causality",
        assumptions=("action_causality_fixture", "nominal_linear"),
        metadata={"suite": "mpc_central", "fork": "charge"},
    )
    obs = _obs_one_vehicle(inst, soc=16.0, released=("Near",))
    return ForkSpec(
        case_id="case_a_predictive_charging",
        instance=inst,
        observation=obs,
        scenarios=((), (("Far", 1.0),)),
        scenario_probs=(0.35, 0.65),
        candidate_actions=("serve_near", "charge_first"),
        notes=(
            "reactive prefers serve_near when Far absent",
            "stochastic with P(Far)=0.65 prefers charge_first",
        ),
    )


def case_b_irreversible_admission_fork() -> ForkSpec:
    """Accept costly Now vs reject to preserve capacity for Future.

    Now is far with long service; Future is close with a tight window after t=5.
    Accepting/serving Now consumes so much time that Future's window is missed.
    Rejecting Now leaves the vehicle free for Future.
    """
    vehicle = VehicleType(100.0, 5.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        Node("S", NodeKind.CHARGER, 1, 1, 0, TimeWindow(0, 300), 0),
        Node("Now", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 80), 12),
        Node("Future", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(5, 28), 1),
    ]
    inst = build_euclidean_instance(
        "mpc_central_case_b_admission_fork",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="mpc_central_causality",
        assumptions=("action_causality_fixture", "nominal_linear"),
        metadata={"suite": "mpc_central", "fork": "admission"},
    )
    obs = _obs_one_vehicle(inst, released=("Now",))
    return ForkSpec(
        case_id="case_b_irreversible_admission",
        instance=inst,
        observation=obs,
        scenarios=((), (("Future", 5.0),)),
        scenario_probs=(0.2, 0.8),
        candidate_actions=("accept_now", "reject_now"),
        notes=(
            "reactive prefers accept_now on visible demand",
            "stochastic with high P(Future) prefers reject_now",
        ),
    )


def all_forks() -> list[ForkSpec]:
    return [case_a_predictive_charging_fork(), case_b_irreversible_admission_fork()]
