"""Gates 1–4: transactional emit, terminal commitment, RF correspondence."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import (
    STATUS_CERTIFIED,
    STATUS_LOST,
    CommitmentSafeStochasticMpc,
)
from safe_time_evrp.mpc_central.terminal_commitment import (
    TerminalRejectReason,
    stage0_ok_but_terminal_counterexample_state,
    terminal_state_from_observation,
    verify_terminal_commitment,
)
from safe_time_evrp.testbed.constructor import make_observation


def _toy():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 100), 5),
        Node("C2", NodeKind.CUSTOMER, 6, 1, 1, TimeWindow(20, 120), 5),
    ]
    return build_euclidean_instance(
        "gate_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="gates",
        assumptions=("gates",),
    )


def test_gate1_invalid_candidate_cannot_introduce_accepts():
    """Adversarial: commit of empty routes + speculative newly must fail; Decision has newly=[]."""
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1", "C2"), (), (), (), (), (), public_customer_count=2)
    ctrl = CommitmentSafeStochasticMpc(
        inst, horizon=80.0, use_forecast=False, alns_iterations=3, time_limit_seconds=0.2, seed=1
    )
    public = make_public_snapshot(inst, obs, 80.0).instance
    # Speculative accept with empty routes — independent validation must fail.
    bad = ctrl._try_commit(
        obs,
        public,
        routes={v.id: [] for v in obs.vehicles},
        newly=["C1"],
        rejected=[],
        deferred=[],
        notes=["adversarial"],
        started=0.0,
        trigger="test",
        fallback_flag=False,
    )
    assert bad is None
    assert ctrl.store.current is None  # nothing published
    # Fallback must not invent accepts.
    out = ctrl._emit_fallback(
        obs,
        public,
        fallback_routes=None,
        notes=["adversarial_fallback"],
        started=0.0,
        trigger="test",
    )
    assert out.newly_accepted == []
    assert "C1" not in out.accepted
    assert out.no_feasible_continuation is True
    # No existing obligations → UNKNOWN is allowed; with obligations would be LOST.
    # Here accepted was empty, so UNKNOWN.
    assert out.audit["css_mpc"]["validation_status"] in {STATUS_LOST, "UNKNOWN"}


def test_gate1_failed_commit_does_not_publish_and_strips_new_accepts():
    inst = _toy()
    base = make_observation(inst, 1)
    # Existing obligation C1 already accepted — RF-critical.
    obs = Observation(0.0, base.vehicles, ("C1", "C2"), ("C1",), (), (), (), (), public_customer_count=2)
    ctrl = CommitmentSafeStochasticMpc(
        inst, horizon=80.0, use_forecast=False, alns_iterations=2, time_limit_seconds=0.15, seed=2
    )
    public = make_public_snapshot(inst, obs, 80.0).instance
    # Publish a good certificate for C1 first.
    good_routes = {
        "v0": [
            Visit("C1", "service"),
            Visit("D0", "return"),
        ]
    }
    ok = ctrl._try_commit(
        obs,
        public,
        routes=good_routes,
        newly=[],
        rejected=[],
        deferred=[],
        notes=[],
        started=0.0,
        trigger="seed",
        fallback_flag=False,
    )
    assert ok is not None
    assert ok.audit["css_mpc"]["validation_status"] == STATUS_CERTIFIED
    assert ctrl.store.current is not None
    published_version = ctrl.store.current.version

    # Now attempt invalid speculative accept of C2 with empty routes.
    bad = ctrl._try_commit(
        obs,
        public,
        routes={v.id: [] for v in obs.vehicles},
        newly=["C2"],
        rejected=[],
        deferred=[],
        notes=[],
        started=0.0,
        trigger="bad",
        fallback_flag=False,
    )
    assert bad is None
    # Store still holds previous good certificate (publish only on success).
    assert ctrl.store.current is not None
    assert ctrl.store.current.version == published_version
    assert "C2" not in ctrl.store.current.accepted

    fb = ctrl._emit_fallback(
        obs,
        public,
        fallback_routes=good_routes,
        notes=[],
        started=0.0,
        trigger="fb",
    )
    assert fb.newly_accepted == []
    assert "C2" not in fb.accepted
    assert "C1" in fb.accepted
    assert fb.audit["css_mpc"]["validation_status"] == STATUS_CERTIFIED


def test_gate1_loss_reported_when_existing_uncovered():
    inst = _toy()
    base = make_observation(inst, 1)
    obs = Observation(0.0, base.vehicles, ("C1",), ("C1",), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(
        inst, horizon=80.0, use_forecast=False, alns_iterations=1, time_limit_seconds=0.1, seed=3
    )
    public = make_public_snapshot(inst, obs, 80.0).instance
    out = ctrl._emit_fallback(
        obs,
        public,
        fallback_routes={v.id: [] for v in obs.vehicles},  # invalid for C1
        notes=[],
        started=0.0,
        trigger="lost",
    )
    assert out.newly_accepted == []
    assert "C1" in out.accepted  # never silently drop existing obligation from Decision.accepted
    assert out.audit["css_mpc"]["validation_status"] == STATUS_LOST
    assert out.no_feasible_continuation is True


def test_gate2_verify_terminal_rejects_stranded_obligation():
    inst, obs, residual = stage0_ok_but_terminal_counterexample_state()
    term = terminal_state_from_observation(obs)
    report = verify_terminal_commitment(
        inst,
        term,
        residual,
        backup_routes={v.id: [] for v in obs.vehicles},
        backup_policy="routes_only",
    )
    assert report.ok is False
    assert report.reason == TerminalRejectReason.TERMINAL_INFEASIBLE


def test_gate2_verify_terminal_ok_when_empty_residual():
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, (), (), ("C1",), (), (), (), public_customer_count=2)
    term = terminal_state_from_observation(obs)
    report = verify_terminal_commitment(inst, term, frozenset(), backup_routes={v.id: [] for v in obs.vehicles})
    assert report.ok is True
    assert report.reason == TerminalRejectReason.OK


def test_gate2_stage0_pass_terminal_constraint_is_distinct():
    """Delegates to the meaningful Phase-1 counterexample (stage0 True, terminal False)."""
    from tests.test_terminal_horizon_correctness import test_stage0_feasible_projected_terminal_infeasible

    test_stage0_feasible_projected_terminal_infeasible()


def test_gate3_rf_emission_never_adds_accept_without_certificate():
    """Algorithm–theorem correspondence: CERTIFIED_FEASIBLE ⇒ store published & newly covered."""
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=2)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=6,
        time_limit_seconds=0.35,
        seed=7,
        require_terminal_commitment=True,
    )
    d = ctrl.decide(obs, "request_release")
    if d.audit["css_mpc"]["validation_status"] == STATUS_CERTIFIED:
        assert ctrl.store.current is not None
        assert set(d.newly_accepted) <= set(ctrl.store.current.accepted)
        assert d.audit["css_mpc"]["published"] is True
        for cid in d.newly_accepted:
            assert cid in d.accepted
    else:
        assert d.newly_accepted == []
        assert d.audit["css_mpc"]["published"] is False


def test_gate3_assumption_counterexample_loss_status():
    """When backup cannot cover existing A_t, status is CERTIFIED_FEASIBILITY_LOST (not silent OK)."""
    inst = _toy()
    base = make_observation(inst, 1)
    obs = Observation(0.0, base.vehicles, ("C1",), ("C1",), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(inst, horizon=50.0, use_forecast=False, time_limit_seconds=0.05, seed=0)
    public = make_public_snapshot(inst, obs, 50.0).instance
    d = ctrl._emit_fallback(obs, public, fallback_routes=None, notes=[], started=0.0, trigger="t")
    assert d.audit["css_mpc"]["validation_status"] == STATUS_LOST
    assert d.newly_accepted == []


def test_approximation_class_documented():
    inst = _toy()
    ctrl = CommitmentSafeStochasticMpc(inst, horizon=40.0, use_forecast=False)
    assert "restricted_candidate_set" in ctrl.approximation_class


def test_ablation_flags_no_charge_and_no_warm_start():
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=2)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=4,
        time_limit_seconds=0.25,
        seed=11,
        allow_charge_candidates=False,
        use_warm_start=False,
    )
    d = ctrl.decide(obs, "request_release")
    assert "allow_charge_candidates=0" in d.notes or "warm_start=0" in d.notes
    assert "warm_start=0" in d.notes
    # No charge first legs among notes/selection path — if selected exists, legs lack charge.
    from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey

    key = FirstActionKey.from_decision(d)
    assert all(leg[2] != "charge" for leg in key.first_legs)
