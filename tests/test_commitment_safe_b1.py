"""B1 full-validation commitment-safe MPC regressions."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.validation.replay import validate_log


def _obs(instance: Instance, released: tuple[str, ...], *, fleet: int = 1, accepted: tuple[str, ...] = ()):
    battery = instance.vehicle_type.battery_capacity
    vehicles = []
    for i in range(fleet):
        anchor = Anchor(instance.depot_id, 0.0, battery, 0.0, frozenset())
        vehicles.append(VehicleView(f"v{i + 1}", "idle", instance.depot_id, battery, 0.0, (), anchor, None))
    return Observation(0.0, tuple(vehicles), released, accepted, (), (), (), ())


def test_validate_continuation_rejects_commitment_breaking_extra():
    """Serving a far extra customer before a tight commitment fails validation."""
    vehicle = VehicleType(100.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = {
        "D": Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        # C1 must be reached by t<=12; detouring via C2 (travel 20) inevitably misses.
        "C1": Node("C1", NodeKind.CUSTOMER, 8, 0, 1, TimeWindow(0, 12), 1),
        "C2": Node("C2", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(0, 200), 1),
    }
    arcs = {
        ("D", "C1"): Arc("D", "C1", 8.0, 8.0, 1.0, "eucl"),
        ("C1", "D"): Arc("C1", "D", 8.0, 8.0, 1.0, "eucl"),
        ("D", "C2"): Arc("D", "C2", 20.0, 20.0, 1.0, "eucl"),
        ("C2", "D"): Arc("C2", "D", 20.0, 20.0, 1.0, "eucl"),
        ("C1", "C2"): Arc("C1", "C2", 12.0, 12.0, 1.0, "eucl"),
        ("C2", "C1"): Arc("C2", "C1", 12.0, 12.0, 1.0, "eucl"),
    }
    inst = Instance("adv", nodes, arcs, vehicle, "D", "synthetic", "t")
    obs = _obs(inst, ("C1", "C2"), fleet=1, accepted=("C1",))
    bad = {"v1": [Visit("C2", "service"), Visit("C1", "service"), Visit("D", "return")]}
    bad_rep = validate_continuation(inst, obs, bad, require_new=frozenset({"C2"}))
    assert not bad_rep.ok
    good = {"v1": [Visit("C1", "service"), Visit("D", "return")]}
    good_rep = validate_continuation(inst, obs, good, require_new=frozenset())
    assert good_rep.ok and "C1" in good_rep.served


def test_b1_rejects_unvalidated_new_accept():
    inst = make_reference_instance("easy")
    ctrl = FullValidationAlnsMpc(inst, 200, iterations=15, time_limit_seconds=0.15, seed=2)
    obs = _obs(inst, ("C1", "C2", "C3"), fleet=2, accepted=("C1",))
    decision = ctrl.decide(obs, "test")
    assert decision.audit["validation_status"] in {"CERTIFIED_FEASIBLE", "UNKNOWN"}
    for cid in decision.newly_accepted:
        rep = validate_continuation(inst, obs, decision.routes, require_new=frozenset(decision.newly_accepted))
        assert rep.ok
        assert cid in rep.served


def test_b1_episode_replays_and_profiles():
    inst = make_reference_instance("easy")
    ctrl = FullValidationAlnsMpc(inst, 200, iterations=20, time_limit_seconds=0.2, seed=3)
    result = run_episode(
        inst,
        [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)],
        fleet_size=2,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
        controller=ctrl,
    )
    assert validate_log(inst, result.log).ok
    assert ctrl.profile.decisions >= 1
    assert ctrl.profile.routes_revalidated >= 1
    assert ctrl.profile.validation_seconds >= 0.0


def test_b1_uses_same_alns_engine():
    inst = make_reference_instance("easy")
    ctrl = FullValidationAlnsMpc(inst, 200, iterations=5, time_limit_seconds=0.05, seed=0)
    assert ctrl._alns.__class__.__name__ == "ReactiveAlnsMpc"
