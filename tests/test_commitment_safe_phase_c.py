"""Phase C: public information boundary + reactive ALNS–MPC."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_compare import run_matched_case
from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.commitment_safe_mpc.phase_b_demo import make_phase_b_instance, phase_b_releases
from safe_time_evrp.commitment_safe_mpc.public_snapshot import (
    assert_no_future_leak,
    make_public_snapshot,
    sanitize_instance,
    visible_customer_ids,
)
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.validation.replay import validate_log


def _obs_partial(instance, released):
    battery = instance.vehicle_type.battery_capacity
    vehicles = []
    for i in range(2):
        anchor = Anchor(instance.depot_id, 0.0, battery, 0.0, frozenset())
        vehicles.append(VehicleView(f"v{i + 1}", "idle", instance.depot_id, battery, 0.0, (), anchor, None))
    return Observation(0.0, tuple(vehicles), tuple(released), (), (), (), (), ())


def test_public_snapshot_excludes_unreleased_customers():
    full = make_phase_b_instance()
    obs = _obs_partial(full, ("C1", "C2"))
    snap = make_public_snapshot(full, obs, horizon=400.0)
    assert_no_future_leak(snap, full)
    public_ids = {c.id for c in snap.instance.customers}
    assert public_ids == {"C1", "C2"}
    assert "C3" not in public_ids and "C4" not in public_ids


def test_identical_histories_identical_decisions_despite_hidden_futures():
    """Two full instances differ only in a still-hidden customer; decisions must match."""
    base = make_reference_instance("easy")
    # Clone geometry but add an extra far-future customer only in instance B's full set
    from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, build_euclidean_instance

    nodes_a = list(base.nodes.values())
    nodes_b = list(base.nodes.values()) + [
        Node("C_HIDDEN", NodeKind.CUSTOMER, 50, 50, 1, TimeWindow(1000, 1100), 1),
    ]
    inst_a = build_euclidean_instance(
        "hist_a", nodes_a, base.vehicle_type, source_format="synthetic", source_name="hist"
    )
    inst_b = build_euclidean_instance(
        "hist_b", nodes_b, base.vehicle_type, source_format="synthetic", source_name="hist"
    )
    obs = _obs_partial(inst_a, ("C1", "C2"))
    # Ensure C_HIDDEN not visible
    assert "C_HIDDEN" not in visible_customer_ids(obs)
    ctrl_a = ReactiveAlnsMpc(inst_a, horizon=200, iterations=15, time_limit_seconds=0.15, seed=1)
    ctrl_b = ReactiveAlnsMpc(inst_b, horizon=200, iterations=15, time_limit_seconds=0.15, seed=1)
    da = ctrl_a.decide(obs, "test")
    db = ctrl_b.decide(obs, "test")
    assert da.planned_service == db.planned_service
    assert da.newly_accepted == db.newly_accepted
    assert da.rejected == db.rejected
    keys_a = [(vid, v.node_id, v.purpose) for vid, visits in da.routes.items() for v in visits]
    keys_b = [(vid, v.node_id, v.purpose) for vid, visits in db.routes.items() for v in visits]
    assert keys_a == keys_b
    # Public sanitize of B must not include hidden
    pub_b = sanitize_instance(inst_b, visible_customer_ids(obs))
    assert "C_HIDDEN" not in {c.id for c in pub_b.customers}


def test_insertion_mpc_uses_public_snapshot():
    full = make_phase_b_instance()
    obs = _obs_partial(full, ("C1",))
    ctrl = EventTriggeredMPC(full, horizon=400)
    decision = ctrl.decide(obs, "test")
    # Must not plan service for unreleased C3/C4
    planned = set(decision.planned_service) | set(decision.newly_accepted)
    assert "C3" not in planned and "C4" not in planned


def test_alns_runs_search_and_replays_on_phase_b():
    inst = make_phase_b_instance()
    ctrl = ReactiveAlnsMpc(inst, horizon=400, iterations=25, time_limit_seconds=0.3, seed=3)
    result = run_episode(
        inst,
        phase_b_releases(),
        fleet_size=2,
        horizon=400,
        max_replan_interval=25,
        t_max=500,
        controller=ctrl,
    )
    report = validate_log(inst, result.log)
    assert report.ok, report.detail
    # At least one decision recorded ALNS search activity
    audits = [(d.audit or {}).get("alns") for d in result.decisions if d.audit]
    assert any(a and (a.get("iterations") or 0) > 0 for a in audits)
    assert any(a and (a.get("candidates_evaluated") or 0) >= 0 for a in audits)


def test_new_accept_requires_served_witness():
    inst = make_reference_instance("easy")
    ctrl = ReactiveAlnsMpc(inst, horizon=200, iterations=20, time_limit_seconds=0.2, seed=2)
    obs = _obs_partial(inst, ("C1", "C2", "C3"))
    decision = ctrl.decide(obs, "test")
    for cid in decision.newly_accepted:
        assert cid in decision.planned_service


def test_matched_easy_case_both_replay():
    suite = build_baseline_suite()
    easy = next(c for c in suite if c.case_id == "B_easy_dynamic")
    row = run_matched_case(easy, alns_iterations=20, alns_time=0.15)
    assert row["insertion"]["replay_ok"]
    assert row["alns"]["replay_ok"]
    assert (row["alns"].get("alns_iterations") or 0) >= 0
