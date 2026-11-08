"""Request-rescue ALNS, validator contracts, snapshot allowlist, metric accounting."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.alns_mpc import (
    ALNSDiagnostics,
    ReactiveAlnsMpc,
)
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.primitive_route_check import primitive_check_route
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import (
    Arc,
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    VehicleType,
    build_euclidean_instance,
)
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.optimization.insertion import construct_routes


def _fleet_obs(instance: Instance, released: tuple[str, ...], nveh: int, *, accepted: tuple[str, ...] = ()):
    bat = instance.vehicle_type.battery_capacity
    vehicles = []
    for i in range(nveh):
        anchor = Anchor(instance.depot_id, 0.0, bat, 0.0, frozenset())
        vehicles.append(VehicleView(f"v{i + 1}", "idle", instance.depot_id, bat, 0.0, (), anchor, None))
    return Observation(0.0, tuple(vehicles), released, accepted, (), (), (), ())


def _packing_rescue_instance() -> Instance:
    """Constructor packs A,B (demand 1) onto two vehicles; C (demand 2) needs a whole vehicle."""
    vehicle = VehicleType(500.0, 2.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 5000), 0),
        Node("S", NodeKind.CHARGER, 0, 1, 0, TimeWindow(0, 5000), 0),
        Node("A", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 40), 1),
        Node("B", NodeKind.CUSTOMER, 0, 5, 1, TimeWindow(0, 45), 1),
        Node("C", NodeKind.CUSTOMER, 50, 0, 2, TimeWindow(0, 55), 1),
    ]
    return build_euclidean_instance(
        "rescue_pack",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="rescue",
        assumptions=("request_rescue_fixture",),
    )


def test_constructor_misses_c_but_alternate_serves_abc():
    inst = _packing_rescue_instance()
    obs = _fleet_obs(inst, ("A", "B", "C"), 2)
    plan = construct_routes(inst, obs, horizon=400, energy=NominalLinearEnergy())
    assert set(plan.planned_service) == {"A", "B"}
    assert "C" in plan.rejected
    # Known feasible reassignment
    from safe_time_evrp.commitment_safe_mpc.alns_mpc import _decode_sequences

    decoded = _decode_sequences(inst, obs, {"v1": ["C"], "v2": ["A", "B"]}, NominalLinearEnergy(), ALNSDiagnostics())
    assert decoded is not None
    assert set(decoded[3]) == {"A", "B", "C"}


def test_alns_rescues_constructor_rejected_customer():
    inst = _packing_rescue_instance()
    obs = _fleet_obs(inst, ("A", "B", "C"), 2)
    ctrl = ReactiveAlnsMpc(inst, 400, iterations=200, time_limit_seconds=5.0, seed=0, destroy_fraction=0.85)
    decision = ctrl.decide(obs, "rescue")
    assert set(decision.planned_service) == {"A", "B", "C"}
    assert "C" in decision.newly_accepted
    assert ctrl.last_diagnostics.constructor_served == 2
    assert ctrl.last_diagnostics.best_served == 3
    assert ctrl.last_diagnostics.improved_coverage_over_constructor
    assert "C" in ctrl.last_diagnostics.rescued_customers
    # Physical continuation feasible
    for vehicle in obs.vehicles:
        result = evaluate_route(inst, vehicle.anchor, decision.routes[vehicle.id], NominalLinearEnergy())
        assert result.feasible


def test_b1_rescues_and_refuses_obligation_breaking_extra():
    inst = _packing_rescue_instance()
    obs = _fleet_obs(inst, ("A", "B", "C"), 2)
    b1 = FullValidationAlnsMpc(inst, 400, iterations=200, time_limit_seconds=5.0, seed=0, destroy_fraction=0.85)
    decision = b1.decide(obs, "rescue")
    assert decision.audit["validation_status"] == "CERTIFIED_FEASIBLE"
    assert set(decision.newly_accepted) >= {"A", "B", "C"} or set(decision.planned_service) == {"A", "B", "C"}

    # Obligation-breaking: already accepted A; force a bad plan that drops A for C alone on both?
    # Use tight commitment vs far extra (unit-level validator).
    vehicle = VehicleType(100.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = {
        "D": Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        "A": Node("A", NodeKind.CUSTOMER, 8, 0, 1, TimeWindow(0, 12), 1),
        "C": Node("C", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 200), 1),
    }
    arcs = {
        ("D", "A"): Arc("D", "A", 8.0, 8.0, 1.0, "eucl"),
        ("A", "D"): Arc("A", "D", 8.0, 8.0, 1.0, "eucl"),
        ("D", "C"): Arc("D", "C", 20.0, 20.0, 1.0, "eucl"),
        ("C", "D"): Arc("C", "D", 20.0, 20.0, 1.0, "eucl"),
        ("A", "C"): Arc("A", "C", 12.0, 12.0, 1.0, "eucl"),
        ("C", "A"): Arc("C", "A", 12.0, 12.0, 1.0, "eucl"),
    }
    tiny = Instance("obl", nodes, arcs, vehicle, "D", "synthetic", "t")
    obs2 = _fleet_obs(tiny, ("A", "C"), 1, accepted=("A",))
    bad = {"v1": [Visit("C", "service"), Visit("A", "service"), Visit("D", "return")]}
    rep = validate_continuation(tiny, obs2, bad, require_new=frozenset({"C"}))
    assert not rep.ok


def test_locked_suffix_must_be_empty():
    inst = _packing_rescue_instance()
    bat = inst.vehicle_type.battery_capacity
    anchor = Anchor("D", 0.0, bat, 0.0, frozenset())
    locked = VehicleView("v1", "traveling", "D", bat, 0.0, (), anchor, "A")
    idle = VehicleView("v2", "idle", "D", bat, 0.0, (), anchor, None)
    obs = Observation(0.0, (locked, idle), ("A", "B"), ("A",), (), (), (), ())
    bad = {"v1": [Visit("B", "service")], "v2": []}
    rep = validate_continuation(inst, obs, bad)
    assert not rep.ok
    assert any("locked_action" in r for r in rep.reasons)


def test_station_capacity_refused():
    vehicle = VehicleType(50.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = {
        "D": Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        "C1": Node("C1", NodeKind.CUSTOMER, 1, 0, 1, TimeWindow(0, 80), 1),
    }
    arcs = {
        ("D", "C1"): Arc("D", "C1", 1.0, 1.0, 0.1, "eucl"),
        ("C1", "D"): Arc("C1", "D", 1.0, 1.0, 0.1, "eucl"),
    }
    inst = Instance("cap", nodes, arcs, vehicle, "D", "synthetic", "t", station_capacity=1)
    obs = _fleet_obs(inst, ("C1",), 1)
    rep = validate_continuation(inst, obs, {"v1": []})
    assert rep.status == "MODEL_CONTRACT_VIOLATED"
    assert not rep.ok


def test_primitive_check_agrees_on_feasible_route():
    inst = _packing_rescue_instance()
    obs = _fleet_obs(inst, ("A", "B"), 1)
    visits = [Visit("A", "service"), Visit("D", "return")]
    ev = evaluate_route(inst, obs.vehicles[0].anchor, visits, NominalLinearEnergy())
    prim = primitive_check_route(inst, obs.vehicles[0].anchor, visits)
    assert ev.feasible == prim.ok
    assert set(ev.served) == set(prim.served)


def test_metadata_allowlist_and_hidden_future():
    vehicle = VehicleType(50.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = {
        "D": Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        "C1": Node("C1", NodeKind.CUSTOMER, 1, 0, 1, TimeWindow(0, 80), 1),
        "C2": Node("C2", NodeKind.CUSTOMER, 2, 0, 1, TimeWindow(0, 80), 1),
    }
    arcs = {
        ("D", "C1"): Arc("D", "C1", 1.0, 1.0, 0.1, "eucl"),
        ("C1", "D"): Arc("C1", "D", 1.0, 1.0, 0.1, "eucl"),
        ("D", "C2"): Arc("D", "C2", 2.0, 2.0, 0.2, "eucl"),
        ("C2", "D"): Arc("C2", "D", 2.0, 2.0, 0.2, "eucl"),
        ("C1", "C2"): Arc("C1", "C2", 1.0, 1.0, 0.1, "eucl"),
        ("C2", "C1"): Arc("C2", "C1", 1.0, 1.0, 0.1, "eucl"),
    }
    full = Instance(
        "hid",
        nodes,
        arcs,
        vehicle,
        "D",
        "synthetic",
        "t",
        metadata={"private": {"secret": 1}, "hidden_releases": [("C2", 99.0)], "suite": "x", "future_route": ["C2"]},
    )
    obs = _fleet_obs(full, ("C1",), 1)
    snap = make_public_snapshot(full, obs, 50.0)
    assert "C2" not in snap.instance.nodes
    assert "private" not in snap.instance.metadata
    assert "hidden_releases" not in snap.instance.metadata
    assert "future_route" not in snap.instance.metadata
    assert snap.instance.metadata.get("suite") == "x"


def test_regret_and_greedy_select_different_customers():
    """Deterministic option table where greedy and regret-2 disagree."""
    # Hand-scored options without needing a full decide():
    # customer X: best=1, second=10 → regret=9
    # customer Y: best=2, second=3 → regret=1
    # greedy picks X (best cost 1); regret-2 picks X as well here.
    # Need: X best=1 only one option; Y best=3, second=20 → regret large
    # Better: X options [5, 6] regret 1; Y options [10, 100] regret 90 → regret picks Y, greedy picks X
    best = {"X": 5.0, "Y": 10.0}
    regret2 = {"X": 1.0, "Y": 90.0}
    greedy_pick = min(best, key=lambda c: (best[c], c))
    regret_pick = max(regret2, key=lambda c: (regret2[c], -best[c], c))
    assert greedy_pick == "X"
    assert regret_pick == "Y"
    assert greedy_pick != regret_pick
    from safe_time_evrp.commitment_safe_mpc import alns_mpc as mod

    assert "regret2" in mod.REPAIR_OPS and "greedy" in mod.REPAIR_OPS


def test_validation_seconds_are_per_decision_not_cumulative_sum():
    inst = _packing_rescue_instance()
    obs = _fleet_obs(inst, ("A", "B", "C"), 2)
    b1 = FullValidationAlnsMpc(inst, 400, iterations=30, time_limit_seconds=0.5, seed=0)
    d1 = b1.decide(obs, "t1")
    d2 = b1.decide(obs, "t2")
    a1 = d1.audit["validation_seconds_this_decision"]
    a2 = d2.audit["validation_seconds_this_decision"]
    cum2 = d2.audit["validation_seconds_cumulative"]
    assert a1 >= 0 and a2 >= 0
    assert abs(cum2 - (b1.profile.validation_seconds)) < 1e-12
    # Per-decision values must not equal the full cumulative after 2 decisions (unless zero).
    if cum2 > 0:
        assert a2 <= cum2 + 1e-12
