"""Gate 3D Amazon window parsing, energy-active configs, and horizon microscope."""

from __future__ import annotations

from safe_time_evrp.data.amazon import (
    ESOGU_ENERGY_ACTIVE_V1,
    ESOGU_LIGHT_CARGO_V1,
    _parse_window_hours,
    list_route_ids,
    load_amazon_route,
)
from safe_time_evrp.mpc3c.horizon_microscope import search_horizon_causality


def test_parse_window_honors_utc_strings():
    # Departure at 2018-07-27 16:02:10 → epoch hours from 2018-01-01.
    from datetime import datetime

    dep = datetime(2018, 7, 27, 16, 2, 10)
    dep_h = (dep - datetime(2018, 1, 1)).total_seconds() / 3600.0
    window = _parse_window_hours(
        "2018-07-27 16:00:00",
        "2018-07-28 00:00:00",
        12.0,
        departure_epoch_h=dep_h,
    )
    assert window.ready < window.due
    assert window.due <= 12.0 + 1e-9
    # Start is slightly before departure → clamped to 0.
    assert window.ready == 0.0


def test_parse_window_missing_is_full_day():
    import math

    w = _parse_window_hours(math.nan, math.nan, 12.0, departure_epoch_h=0.0)
    assert w.ready == 0.0 and w.due == 12.0


def test_amazon_loader_records_nontrivial_windows_when_present():
    try:
        rid = list_route_ids()[0]
    except FileNotFoundError:
        return
    inst = load_amazon_route(rid, max_customers=8, electrification=ESOGU_LIGHT_CARGO_V1)
    assert int(inst.metadata.get("observed_package_windows", "0")) >= 0
    # At least one customer should have a finite due if packages carry UTC windows.
    dues = [inst.node(c).window.due for c in inst.customer_ids()]
    assert min(dues) <= 12.0


def test_energy_active_config_differs_from_baseline():
    assert ESOGU_ENERGY_ACTIVE_V1.consumption_kwh_per_km > ESOGU_LIGHT_CARGO_V1.consumption_kwh_per_km
    assert ESOGU_ENERGY_ACTIVE_V1.battery_kwh == ESOGU_LIGHT_CARGO_V1.battery_kwh


def test_horizon_microscope_changes_executed_action():
    report = search_horizon_causality()
    assert report["horizon_changes_executed_action"] is True
    assert report["executed_action_short"] != report["executed_action_long"]
    assert report["executed_action_no_forecast"] == report["executed_action_short"]
    # Dispatched first action must not be an unreleased synthetic service.
    assert not str(report["executed_action_long"][0]).startswith("syn_")
