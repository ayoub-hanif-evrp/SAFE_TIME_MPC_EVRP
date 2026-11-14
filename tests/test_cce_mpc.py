"""CC-E-MPC: oracle charge, anti-always-charge, certificate theory smoke."""

from __future__ import annotations

from safe_time_evrp.mpc_central.certificate_theory import theorem_document
from safe_time_evrp.mpc_central.final_mpc_package import (
    anti_always_charge_test,
    live_oracle_charge_test,
)


def test_theorem_is_nominal_not_robust():
    doc = theorem_document()
    assert doc["supported_by_plant"] is True
    assert any("misspecification" in x.lower() or "disturb" in x.lower() for x in doc["what_is_not_claimed"])


def test_live_oracle_selects_charge_first():
    report = live_oracle_charge_test(seed=0)
    assert report["charge_beats_serve_in_reference"] is True
    assert abs(report["reference"]["charge_first"]["mean_value"] - 122.29) < 0.5
    assert abs(report["reference"]["serve_near"]["mean_value"] - 88.0) < 0.5
    assert report["live_selected_charge"] is True
    assert report["pass"] is True


def test_anti_always_charge():
    report = anti_always_charge_test(seed=0)
    assert report["pass"] is True
    assert report["selected_charge"] is False


def test_certificate_regressions_and_package_import():
    from safe_time_evrp.mpc_central.final_mpc_package import certificate_event_regressions

    cert = certificate_event_regressions(seed=7)
    assert cert["pass"] is True
    assert cert["replay_ok"] is True
    assert cert["illegal_admission_blocked"] is True
    # Full matched eval is executed in final_mpc_package.__main__ / docs generation, not every CI unit.
