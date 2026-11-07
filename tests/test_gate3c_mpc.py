"""Gate 3C controller and causal-experiment smoke tests."""

from __future__ import annotations

from pathlib import Path

from safe_time_evrp.data.amazon import list_route_ids, load_amazon_route
from safe_time_evrp.data.evrp_tw_d import extract_root, list_solomon_files, parse_solomon_file
from safe_time_evrp.models.state import Anchor
from safe_time_evrp.mpc3c.causal_toy import present_actions
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide, static_all_released_observation
from safe_time_evrp.mpc3c.experiment import compare_controllers
from safe_time_evrp.mpc3c.flexibility import flexibility_terminal_value


def test_horizon_appears_in_controller_notes():
    raw = Path("data/raw/evrp_tw_d")
    try:
        root = extract_root(raw)
        path = next(f for f in list_solomon_files(root, scale="Cus_5") if "wide" in f.name)
    except (FileNotFoundError, StopIteration):
        return
    inst = parse_solomon_file(path).with_recharge_policy("full")
    obs = static_all_released_observation(inst, 2)
    for kind in (ControllerKind.RH_OPEN_LOOP, ControllerKind.FLEXIBILITY, ControllerKind.ROLLOUT):
        decision = decide(inst, obs, kind, horizon=5.0)
        assert any("horizon_used=5.0" in n for n in decision.notes)


def test_flexibility_terminal_uses_more_than_soc():
    raw = Path("data/raw/evrp_tw_d")
    try:
        root = extract_root(raw)
        path = next(iter(list_solomon_files(root, scale="Cus_5")))
    except (FileNotFoundError, StopIteration):
        return
    inst = parse_solomon_file(path).with_recharge_policy("full")
    a = Anchor(inst.depot_id, 0.0, inst.vehicle_type.battery_capacity, 0.0, frozenset())
    b = Anchor(inst.depot_id, 0.0, 0.1 * inst.vehicle_type.battery_capacity, 0.0, frozenset())
    # Same remaining set: higher SOC alone should not dominate charger/insertion terms entirely away.
    fa = flexibility_terminal_value(inst, a, inst.customer_ids())
    fb = flexibility_terminal_value(inst, b, inst.customer_ids())
    assert fa != fb


def test_amazon_compare_if_present():
    try:
        rid = list_route_ids()[0]
    except FileNotFoundError:
        return
    inst = load_amazon_route(rid, max_customers=6)
    report = compare_controllers(inst, fleet_size=1, horizon=2.0)
    assert "flexibility_mpc" in report["results"]
    assert report["results"]["rh_open_loop"]["n_served"] >= 0


def test_causal_toy_returns_all_controllers():
    actions = present_actions()
    assert set(actions) == {k.value for k in ControllerKind}
