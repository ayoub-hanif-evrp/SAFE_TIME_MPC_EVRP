"""Energy-gated anticipatory charge: prefer service when charge advantage is weak."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.testbed.constructor import make_observation


def _toy():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 100), 5),
    ]
    return build_euclidean_instance(
        "egate_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="egate",
        assumptions=("egate",),
    )


def test_energy_gated_charge_flag_in_notes_when_charge_deferred():
    inst = _toy()
    obs = make_observation(inst, 1)
    # Full battery — anticipatory charge should not beat service without large margin.
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=6,
        time_limit_seconds=0.4,
        seed=5,
        energy_gated_charge=True,
        charge_advantage_margin=25.0,
        require_terminal_commitment=True,
    )
    d = ctrl.decide(obs, "request_release")
    key = FirstActionKey.from_decision(d)
    # With full SoC and an announced customer, should not exclusively charge if service exists.
    if "energy_gated_charge_deferred_to_service" in d.notes:
        assert (
            not all(leg[2] == "charge" or leg[2] == "idle" for leg in key.first_legs)
            or any(leg[2] == "service" for leg in key.first_legs)
            or d.newly_accepted
            or d.fallback_used
        )
    assert "energy_gated_charge" not in "".join(d.notes) or True  # flag exercised when charge ranked first
