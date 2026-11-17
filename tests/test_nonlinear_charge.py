"""Nonlinear piecewise charging is the only charge model."""

from __future__ import annotations

from safe_time_evrp.environment.energy import NonlinearPiecewiseChargeEnergy


def test_full_charge_matches_scale_time():
    e = NonlinearPiecewiseChargeEnergy()
    q = 100.0
    g = 0.5
    t = e.charge_duration(0.0, q, g, battery_capacity=q)
    assert abs(t - g * q) < 1e-6


def test_near_full_is_slower_than_empty_segment():
    e = NonlinearPiecewiseChargeEnergy()
    q = 100.0
    g = 1.0
    # Same energy delta (10 units) near empty vs near full.
    t_low = e.charge_duration(0.0, 10.0, g, battery_capacity=q)
    t_high = e.charge_duration(85.0, 95.0, g, battery_capacity=q)
    assert t_high > t_low


def test_no_linear_formula_for_partial():
    e = NonlinearPiecewiseChargeEnergy()
    q = 80.0
    g = 0.25
    soc, tgt = 10.0, 50.0
    nonlinear = e.charge_duration(soc, tgt, g, battery_capacity=q)
    linear = g * (tgt - soc)
    assert abs(nonlinear - linear) > 1e-3


def test_linear_ablation_differs_near_full():
    from safe_time_evrp.environment.energy import LinearChargeEnergy

    nl = NonlinearPiecewiseChargeEnergy()
    lin = LinearChargeEnergy()
    q, g = 100.0, 1.0
    soc, tgt = 85.0, 95.0
    assert lin.charge_duration(soc, tgt, g, battery_capacity=q) == g * (tgt - soc)
    assert nl.charge_duration(soc, tgt, g, battery_capacity=q) > lin.charge_duration(
        soc, tgt, g, battery_capacity=q
    )


def test_mechanism_demo_linear_ok_nonlinear_reject():
    from safe_time_evrp.mpc_central.mpc_nonlinear_ev_ablation import (
        _mechanism_charge_mismatch_demo,
    )

    demo = _mechanism_charge_mismatch_demo()
    assert demo["mechanism_holds"] is True
    assert demo["linear_validate_ok"] is True
    assert demo["nonlinear_validate_ok"] is False
