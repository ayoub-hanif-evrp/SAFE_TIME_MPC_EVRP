"""SPI selection law: GN-scored base; CRN override only with verified advantage."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.testbed.constructor import make_observation


def _toy_serve():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 100), 5),
    ]
    return build_euclidean_instance(
        "spi_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="spi",
        assumptions=("spi",),
    )


def test_spi_mode_freezes_legacy_knobs():
    inst = _toy_serve()
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        spi_mode=True,
        energy_gated_charge=True,
        forecast_override_margin=10.0,
    )
    assert ctrl.spi_mode is True
    assert ctrl.energy_gated_charge is False
    assert ctrl.forecast_override_margin is None


def test_spi_notes_and_prefers_service_on_trivial_announce():
    """On a trivial serve-available announce, SPI should not idle/charge-only when GN serves."""
    inst = _toy_serve()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=8,
        time_limit_seconds=0.5,
        seed=3,
        spi_mode=True,
        spi_advantage_margin=0.0,
        require_terminal_commitment=True,
    )
    d = ctrl.decide(obs, "request_release")
    joined = " ".join(d.notes)
    assert "selection_law=spi_crn" in joined
    assert "spi_keep" in joined or "spi_override" in joined or "spi_no_base" in joined
    assert "spi_base=greedy_nominal:" in joined or "spi_no_base" in joined
    key = FirstActionKey.from_decision(d)
    charge_or_idle_only = key.first_legs and all(
        leg[2] in ("charge", "idle", "wait") for leg in key.first_legs
    )
    if not d.fallback_used:
        assert d.newly_accepted or not charge_or_idle_only or "C1" in d.rejected
    if "spi_base=greedy_nominal" in joined:
        assert "spi_crn_advantage=" in joined


def test_legacy_mode_restores_energy_gate_flag():
    inst = _toy_serve()
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        spi_mode=False,
        energy_gated_charge=True,
        forecast_override_margin=5.0,
    )
    assert ctrl.energy_gated_charge is True
    assert ctrl.forecast_override_margin == 5.0


def test_spi_matches_gn_first_action_when_no_override():
    """Stage-0-matched SPI base: CSS first-action newly/legs match GN under shared seed when SPI keeps."""
    from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc

    inst = _toy_serve()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    common = dict(
        horizon=80.0,
        alns_iterations=8,
        time_limit_seconds=0.5,
        seed=3,
        max_replan_interval=30.0,
        rollout_max_events=40,
    )
    gn = CertificateCarryingEconomicMpc(
        inst,
        forecast=None,
        n_scenarios=1,
        use_forecast=False,
        scoring_mode="greedy_nominal",
        use_persistent_certificate=True,
        **common,
    )
    css = CommitmentSafeStochasticMpc(
        inst,
        use_forecast=False,
        n_scenarios=1,
        require_terminal_commitment=True,
        spi_mode=True,
        spi_advantage_margin=1e9,  # force keep GN base (no CRN override)
        **common,
    )
    d_gn = gn.decide(obs, "request_release")
    d_css = css.decide(obs, "request_release")
    joined = " ".join(d_css.notes)
    assert "selection_law=spi_crn" in joined
    assert "spi_keep" in joined or "spi_no_base" in joined
    assert "spi_override" not in joined
    key_gn = FirstActionKey.from_decision(d_gn)
    key_css = FirstActionKey.from_decision(d_css)
    assert tuple(sorted(d_css.newly_accepted or ())) == tuple(sorted(d_gn.newly_accepted or ()))
    assert key_css.first_legs == key_gn.first_legs
