"""Urgent M1 repairs: false certificates, freight-aware prefix, real incremental eval."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.route_resource_profile import (
    EvalMode,
    EvalStats,
    build_profile,
    evaluate_with_profile,
    longest_reusable_prefix_for,
)
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit


def _tiny():
    vehicle = VehicleType(100.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = {
        "D": Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        "A": Node("A", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 100), 1),
        "B": Node("B", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 200), 1),
    }
    arcs = {
        ("D", "A"): Arc("D", "A", 5.0, 5.0, 1.0, "eucl"),
        ("A", "D"): Arc("A", "D", 5.0, 5.0, 1.0, "eucl"),
        ("D", "B"): Arc("D", "B", 10.0, 10.0, 2.0, "eucl"),
        ("B", "D"): Arc("B", "D", 10.0, 10.0, 2.0, "eucl"),
        ("A", "B"): Arc("A", "B", 5.0, 5.0, 1.0, "eucl"),
        ("B", "A"): Arc("B", "A", 5.0, 5.0, 1.0, "eucl"),
    }
    return Instance("tiny", nodes, arcs, vehicle, "D", "synthetic", "t")


def test_onboard_without_future_service_is_not_certified():
    """Critical false-certificate counterexample."""
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    # Parcel A onboard, idle at depot, plan is only return — A never served.
    anchor = Anchor("D", 0.0, bat, 1.0, frozenset({"A"}))
    view = VehicleView("v1", "idle", "D", bat, 1.0, ("A",), anchor, None)
    obs = Observation(0.0, (view,), ("A",), ("A",), (), (), (), ())
    routes = {"v1": [Visit("D", "return")]}
    rep = validate_continuation(inst, obs, routes)
    assert not rep.ok
    assert any("missing_commitments" in r for r in rep.reasons)


def test_traveling_to_a_without_service_continuation_rejected():
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    # Post-arrival anchor at A; locked travel to A; empty suffix → no service of A
    anchor = Anchor("A", 5.0, bat - 1.0, 1.0, frozenset({"A"}))
    view = VehicleView("v1", "traveling", "D", bat, 1.0, ("A",), anchor, "A")
    obs = Observation(0.0, (view,), ("A",), ("A",), (), (), (), ())
    rep = validate_continuation(inst, obs, {"v1": []})
    assert not rep.ok
    assert any("missing_commitments" in r or "locked_travel_without" in r for r in rep.reasons)


def test_traveling_to_a_with_service_suffix_ok():
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    anchor = Anchor("A", 5.0, bat - 1.0, 1.0, frozenset({"A"}))
    view = VehicleView("v1", "traveling", "D", bat, 1.0, ("A",), anchor, "A")
    obs = Observation(0.0, (view,), ("A",), ("A",), (), (), (), ())
    routes = {"v1": [Visit("A", "service"), Visit("D", "return")]}
    rep = validate_continuation(inst, obs, routes)
    assert rep.ok
    assert "A" in rep.served


def test_freight_manifest_blocks_false_prefix_reuse():
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    anchor = Anchor("D", 0.0, bat, 0.0, frozenset())
    old = build_profile(inst, anchor, [Visit("A", "service")])
    assert old.feasible
    [Visit("A", "service"), Visit("B", "service"), Visit("D", "return")]
    # Normalize like evaluator
    from safe_time_evrp.commitment_safe_mpc.route_resource_profile import _normalize_visits

    planned = _normalize_visits(inst, [Visit("A", "service"), Visit("B", "service")])
    pref = longest_reusable_prefix_for(old, planned, anchor, inst.depot_id)
    assert pref == 0, "D-A-D vs D-A-B-D must not reuse prefix A (different depot freight)"


def test_incremental_agrees_with_full_and_avoids_evaluate_route():
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    anchor = Anchor("D", 0.0, bat, 0.0, frozenset())
    energy = NominalLinearEnergy()
    stats0 = EvalStats()
    r0, prof = evaluate_with_profile(
        inst, anchor, [Visit("A", "service")], energy=energy, mode=EvalMode.FULL_EVALUATION, stats=stats0
    )
    assert r0.feasible and prof is not None

    # Same route again — incremental should avoid full evaluate_route on hot path
    stats1 = EvalStats()
    r1, _ = evaluate_with_profile(
        inst,
        anchor,
        [Visit("A", "service")],
        energy=energy,
        mode=EvalMode.INCREMENTAL_EVALUATION,
        previous=prof,
        stats=stats1,
    )
    full = evaluate_route(inst, anchor, [Visit("A", "service")], energy)
    assert r1.feasible == full.feasible
    assert set(r1.served) == set(full.served)
    assert abs(r1.distance - full.distance) < 1e-9
    assert stats1.full_calls_avoided >= 1
    assert stats1.evaluate_route_calls == 0

    # Extend with B — manifest change → recompute from scratch via propagate, still no evaluate_route
    stats2 = EvalStats()
    r2, _ = evaluate_with_profile(
        inst,
        anchor,
        [Visit("A", "service"), Visit("B", "service")],
        energy=energy,
        mode=EvalMode.INCREMENTAL_EVALUATION,
        previous=prof,
        stats=stats2,
    )
    full2 = evaluate_route(inst, anchor, [Visit("A", "service"), Visit("B", "service")], energy)
    assert r2.feasible == full2.feasible
    assert set(r2.served) == set(full2.served)
    assert abs(r2.distance - full2.distance) < 1e-9
    assert stats2.evaluate_route_calls == 0


def test_certificate_advances_after_service_completion():
    inst = _tiny()
    bat = inst.vehicle_type.battery_capacity
    store = CertificateStore()
    a0 = Anchor("D", 0.0, bat, 0.0, frozenset())
    v0 = VehicleView("v1", "idle", "D", bat, 0.0, (), a0, None)
    obs0 = Observation(0.0, (v0,), ("A", "B"), ("A", "B"), (), (), (), ())
    routes = {"v1": [Visit("A", "service"), Visit("B", "service"), Visit("D", "return")]}
    store.publish(routes, obs0, ["A", "B"])

    # Later: A completed, vehicle post-action at A ready for B
    a1 = Anchor("A", 6.0, bat - 1.0, 0.0, frozenset())
    v1 = VehicleView("v1", "idle", "A", bat - 1.0, 0.0, (), a1, None)
    obs1 = Observation(6.0, (v1,), ("B",), ("B",), ("A",), (), (), ())
    advanced = store.advance_or_invalidate(obs1)
    assert advanced is not None
    assert all(v.node_id != "A" or v.purpose != "service" for v in advanced.routes["v1"])
    # B should still be planned
    assert any(v.node_id == "B" and v.purpose == "service" for v in advanced.routes["v1"])
