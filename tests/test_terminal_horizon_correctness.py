"""Phase 1: terminal horizon freeze + residual obligation accounting."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc_central.scenario_rollout import seed_simulator_from_observation
from safe_time_evrp.mpc_central.terminal_commitment import (
    TerminalRejectReason,
    freeze_simulator_at_horizon,
    project_to_horizon,
    residual_obligations_from_observation,
    stage0_ok_but_terminal_counterexample_state,
    terminal_state_from_observation,
    verify_terminal_commitment,
)
from safe_time_evrp.testbed.constructor import make_observation


def _line_instance(*, battery=80.0, far=40.0, due=80.0, service=5.0):
    vehicle = VehicleType(battery, 20.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, far, 0, 1, TimeWindow(0, due), service),
    ]
    return build_euclidean_instance(
        "term_h",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="term_h",
        assumptions=("term_h",),
    )


def test_freeze_advances_clock_with_no_events():
    inst = _line_instance()
    obs = make_observation(inst, 1)
    sim = seed_simulator_from_observation(inst, obs, energy=NominalLinearEnergy())
    assert sim.next_event_time() is None
    notes = freeze_simulator_at_horizon(sim, 25.0)
    assert abs(sim.time - 25.0) < 1e-9
    assert any(n.startswith("clock=") for n in notes)
    assert abs(sim.observation().time - 25.0) < 1e-9


def test_freeze_partial_travel_crossing_horizon():
    inst = _line_instance(far=50.0, battery=100.0)
    obs = make_observation(inst, 1)
    sim = seed_simulator_from_observation(inst, obs, energy=NominalLinearEnergy())
    d = Decision(
        time=0.0,
        routes={"v0": [Visit("C1", "service"), Visit("D0", "return")]},
        accepted=["C1"],
        newly_accepted=["C1"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C1"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    sim.apply_decision(d)
    # Travel C1 takes time 50; freeze at 20 → partial travel.
    notes = freeze_simulator_at_horizon(sim, 20.0)
    assert abs(sim.time - 20.0) < 1e-9
    assert any("partial_travel" in n for n in notes)
    v = sim.vehicles["v0"]
    assert v.status.value == "traveling"
    assert v.soc < inst.vehicle_type.battery_capacity - 1e-6  # energy spent
    assert abs(sim.observation().time - 20.0) < 1e-9


def test_freeze_partial_charge_crossing_horizon():
    inst = _line_instance(battery=100.0)
    # Start nearly empty so full recharge is long (inv=0.5 → duration 50).
    base = make_observation(inst, 1)
    from safe_time_evrp.models.state import Anchor, VehicleView

    v0 = base.vehicles[0]
    low = VehicleView(v0.id, "idle", "S0", 0.0, 0.0, (), Anchor("S0", 0.0, 0.0, 0.0, frozenset()), None)
    obs = Observation(0.0, (low,), (), (), (), (), (), (), public_customer_count=1)
    sim = seed_simulator_from_observation(inst, obs, energy=NominalLinearEnergy())
    d = Decision(
        time=0.0,
        routes={"v0": [Visit("S0", "charge")]},
        accepted=[],
        newly_accepted=[],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=[],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    sim.apply_decision(d)
    notes = freeze_simulator_at_horizon(sim, 10.0)
    assert any("partial_charge" in n for n in notes)
    assert sim.vehicles["v0"].status.value == "charging"
    assert 0.0 < sim.vehicles["v0"].soc < 100.0
    assert abs(sim.time - 10.0) < 1e-9


def test_residual_includes_recourse_accepted_not_candidate_only():
    inst = _line_instance()
    obs = make_observation(inst, 1)
    # Terminal observation where recourse accepted C1 (not in a stale candidate.accepted=[] sense).
    term_obs = Observation(
        10.0,
        obs.vehicles,
        ("C1",),
        ("C1",),
        (),
        (),
        (),
        (),
        public_customer_count=1,
    )
    residual = residual_obligations_from_observation(term_obs)
    assert residual == frozenset({"C1"})
    # in_service also counted
    term2 = Observation(
        10.0,
        obs.vehicles,
        ("C1",),
        (),
        (),
        (),
        ("C1",),
        (),
        public_customer_count=1,
    )
    assert "C1" in residual_obligations_from_observation(term2)


def test_stranded_terminal_battery_infeasible():
    inst, obs, residual = stage0_ok_but_terminal_counterexample_state(battery=5.0)
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


def test_stage0_feasible_projected_terminal_infeasible():
    """Meaningful Gate-2: stage-0 Validate True; short-horizon projection terminal False."""
    from safe_time_evrp.models.state import Anchor, VehicleView

    vehicle = VehicleType(200.0, 10.0, 1.0, 1.0, 1.0, "full")  # slow charge: inv=1 → 200s full
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S0", NodeKind.CHARGER, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("C_far", NodeKind.CUSTOMER, 40, 0, 1, TimeWindow(0, 400), 5),
    ]
    inst = build_euclidean_instance(
        "s0_ok_t_bad",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="gate2",
        assumptions=("gate2",),
    )
    base = make_observation(inst, 1)
    # Start empty at depot/charger so a stage-0 reload+charge+serve plan is needed and feasible.
    v0 = base.vehicles[0]
    empty = VehicleView(v0.id, "idle", "D0", 0.0, 0.0, (), Anchor("D0", 0.0, 0.0, 0.0, frozenset()), None)
    obs = Observation(0.0, (empty,), ("C_far",), (), (), (), (), (), public_customer_count=1)
    public = make_public_snapshot(inst, obs, 200.0).instance
    stage0_routes = {
        "v0": [
            Visit("D0", "reload"),
            Visit("S0", "charge"),
            Visit("C_far", "service"),
            Visit("D0", "return"),
        ]
    }
    stage0 = validate_continuation(
        public, obs, stage0_routes, energy=NominalLinearEnergy(), require_new=frozenset({"C_far"})
    )
    assert stage0.ok is True, stage0.reasons

    # First action starts a long full recharge while accepting C_far; short H freezes mid-charge
    # with too little remaining time/SoC to serve C_far by due=70.
    cand = Decision(
        time=0.0,
        routes={
            "v0": [
                Visit("D0", "reload"),
                Visit("S0", "charge"),
                Visit("C_far", "service"),
                Visit("D0", "return"),
            ]
        },
        accepted=["C_far"],
        newly_accepted=["C_far"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C_far"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    # Horizon 30: still charging (full charge duration = 100); residual C_far cannot be covered
    # by an empty routes_only backup at the frozen state.
    report, _last = project_to_horizon(inst, obs, cand, [], horizon=30.0, max_replan_interval=100.0)
    term = report.terminal_state
    assert term is not None
    assert abs(term.time - 30.0) < 1e-6
    residual = residual_obligations_from_observation(term.observation)
    assert "C_far" in residual
    forced = verify_terminal_commitment(
        inst,
        term,
        residual,
        backup_routes={"v0": []},
        backup_policy="routes_only",
    )
    assert forced.ok is False
    assert forced.reason == TerminalRejectReason.TERMINAL_INFEASIBLE
    assert stage0.ok is True


def test_project_to_horizon_sets_clock_exactly():
    inst = _line_instance(far=10.0)
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    cand = Decision(
        time=0.0,
        routes={"v0": [Visit("C1", "service"), Visit("D0", "return")]},
        accepted=["C1"],
        newly_accepted=["C1"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C1"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    # Horizon before any event completes if we use tiny H after idle? After apply, travel starts.
    report, _ = project_to_horizon(inst, obs, cand, [], horizon=3.0)
    assert report.terminal_state is not None
    assert abs(report.terminal_state.time - 3.0) < 1e-6
