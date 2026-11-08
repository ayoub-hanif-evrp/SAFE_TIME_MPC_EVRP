"""Phase A: D1–D4 policy-class alignment regressions."""

from __future__ import annotations

from safe_time_evrp.dr_dual.generic.policy_class import RESTRICTED_CONTINUATION_MAX_LEN
from safe_time_evrp.dr_dual.generic.scenario_diagnostics import run_all_diagnostics


def test_restricted_horizon_constant():
    assert RESTRICTED_CONTINUATION_MAX_LEN >= 6


def test_d1_d4_unpruned_and_generic_agree_with_exact():
    rows = run_all_diagnostics()
    assert len(rows) == 4
    assert all(r.agrees_unpruned for r in rows)
    assert all(r.agrees_generic for r in rows)
    assert all(r.trajectory_ok_theta0 and r.trajectory_ok_theta1 for r in rows)
    # D2 must exercise a second-vehicle first action at the restricted optimum
    d2 = next(r for r in rows if r.instance_id == "D2_two_ev")
    assert d2.exact_first is not None and "v2" in d2.exact_first
    # D4 must prefer informative first travel under the shared horizon
    d4 = next(r for r in rows if r.instance_id == "D4_info")
    assert d4.exact_first is not None and "inform" in d4.exact_first
