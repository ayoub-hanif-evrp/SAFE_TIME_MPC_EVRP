"""Hand-crafted microscopic forks for MPC action-causality / decision-regret gates."""

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
    base_releases: tuple[tuple[str, float], ...] = ()
    prior_accepted: tuple[str, ...] = ()
    t_max: float = 400.0


def _obs_one_vehicle(
    inst: Instance,
    *,
    soc: float | None = None,
    released: tuple[str, ...] = (),
    accepted: tuple[str, ...] = (),
) -> Observation:
    bat = inst.vehicle_type.battery_capacity if soc is None else soc
    anchor = Anchor(inst.depot_id, 0.0, bat, 0.0, frozenset())
    v = VehicleView("v1", "idle", inst.depot_id, bat, 0.0, (), anchor, None)
    return Observation(0.0, (v,), released, accepted, (), (), (), ())


def case_a_predictive_charging_fork() -> ForkSpec:
    """Serve Near now vs charge first under possible far future demand.

    Battery capacity equals the intended start SOC so FleetSimulator init logs match
    (replay rejects silently patched SOC).
    """
    vehicle = VehicleType(16.0, 5.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 0, 3, 0, TimeWindow(0, 500), 0),
        Node("Near", NodeKind.CUSTOMER, 6, 0, 1, TimeWindow(0, 200), 8),
        Node("Far", NodeKind.CUSTOMER, 0, 9, 1, TimeWindow(0, 28), 1),
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
    obs = _obs_one_vehicle(inst, released=("Near",))
    return ForkSpec(
        case_id="case_a_predictive_charging",
        instance=inst,
        observation=obs,
        scenarios=((), (("Far", 1.0),)),
        scenario_probs=(0.35, 0.65),
        candidate_actions=("serve_near", "charge_first"),
        notes=("reactive prefers serve_near", "stochastic prefers charge_first under P(Far)=0.65"),
        base_releases=(("Near", 0.0),),
        t_max=500.0,
    )


def case_b_irreversible_admission_fork() -> ForkSpec:
    """Accept costly Now vs reject to preserve a pair of future close customers.

    If Now is accepted, the long trip/service makes both FutureA/B miss their windows.
    If Now is rejected, both futures are serviceable when the high-probability scenario occurs.
    """
    vehicle = VehicleType(100.0, 5.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        Node("S", NodeKind.CHARGER, 1, 1, 0, TimeWindow(0, 300), 0),
        Node("Now", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 80), 12),
        Node("FutureA", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(5, 30), 1),
        Node("FutureB", NodeKind.CUSTOMER, 0, 3, 1, TimeWindow(5, 32), 1),
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
        scenarios=((), (("FutureA", 5.0), ("FutureB", 5.0))),
        scenario_probs=(0.2, 0.8),
        candidate_actions=("accept_now", "reject_now"),
        notes=("reactive prefers accept_now", "stochastic prefers reject_now under high P(futures)"),
        base_releases=(("Now", 0.0),),
        t_max=300.0,
    )


def case_c_commitment_plus_uncertain_demand() -> ForkSpec:
    """Already-accepted Must must stay feasible while deciding about optional Now vs Future.

    Must is close and already accepted. Now is a tempting far optional request.
    Future is a nearby opportunity. Accepting Now risks Must and/or Future under time pressure.
    """
    vehicle = VehicleType(100.0, 3.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 400), 0),
        Node("S", NodeKind.CHARGER, 1, 1, 0, TimeWindow(0, 400), 0),
        # demand 2 + Now demand 2 exceeds load capacity 3 → cannot serve both in one tour
        Node("Must", NodeKind.CUSTOMER, 4, 0, 2, TimeWindow(0, 60), 2),
        Node("Now", NodeKind.CUSTOMER, 22, 0, 2, TimeWindow(0, 90), 10),
        Node("Future", NodeKind.CUSTOMER, 2, 3, 1, TimeWindow(8, 35), 1),
    ]
    inst = build_euclidean_instance(
        "mpc_central_case_c_commitment",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="mpc_central_causality",
        assumptions=("action_causality_fixture", "prior_commitment"),
        metadata={"suite": "mpc_central", "fork": "commitment"},
    )
    obs = _obs_one_vehicle(inst, released=("Must", "Now"), accepted=("Must",))
    return ForkSpec(
        case_id="case_c_commitment_plus_uncertain",
        instance=inst,
        observation=obs,
        scenarios=((), (("Future", 8.0),)),
        scenario_probs=(0.3, 0.7),
        candidate_actions=("accept_now", "reject_now", "serve_must"),
        notes=(
            "Must is a hard prior commitment",
            "reject_now or serve_must should dominate accept_now when Future is likely",
        ),
        base_releases=(("Must", 0.0), ("Now", 0.0)),
        prior_accepted=("Must",),
        t_max=400.0,
    )


def all_forks() -> list[ForkSpec]:
    return [
        case_a_predictive_charging_fork(),
        case_b_irreversible_admission_fork(),
        case_c_commitment_plus_uncertain_demand(),
    ]


def phase3_forks() -> list[ForkSpec]:
    """Original Phase-3 pair (no prior commitment)."""
    return [case_a_predictive_charging_fork(), case_b_irreversible_admission_fork()]
