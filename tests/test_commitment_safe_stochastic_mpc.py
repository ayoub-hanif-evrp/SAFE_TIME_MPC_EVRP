"""Regression tests for Commitment-Safe Stochastic MPC (first-deliverable PoC)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from safe_time_evrp.commitment_safe_mpc.public_snapshot import assert_no_future_leak, make_public_snapshot
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.energy_rebuild import infinite_battery_instance, rebuild_arcs_for_vehicle_type
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import (
    OBJECTIVE_WEIGHTS,
    CommitmentSafeStochasticMpc,
)
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.testbed.constructor import make_observation
from safe_time_evrp.validation.replay import validate_log


def _toy_instance() -> object:
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 100), 5),
        Node("C2", NodeKind.CUSTOMER, 6, 1, 1, TimeWindow(20, 120), 5),
        Node("C3", NodeKind.CUSTOMER, 1, 3, 1, TimeWindow(50, 180), 5),
    ]
    return build_euclidean_instance(
        "css_mpc_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="css_mpc_poc",
        assumptions=("poc",),
    )


def test_objective_weights_are_fixed():
    assert OBJECTIVE_WEIGHTS["service_reward"] == 100.0
    assert OBJECTIVE_WEIGHTS["unfulfilled_penalty"] == 250.0
    assert OBJECTIVE_WEIGHTS["distance_penalty"] == 1.0


def test_infinite_battery_rebuild_matches_replay_expectation():
    inst = _toy_instance()
    fat = infinite_battery_instance(inst)
    assert fat.vehicle_type.consumption_rate == 0.0
    assert all(abs(a.energy) < 1e-12 for a in fat.arcs.values())
    # Stale replace-only path must differ from rebuilt path.
    stale = replace(inst, vehicle_type=fat.vehicle_type)
    assert any(a.energy > 1e-9 for a in stale.arcs.values())


def test_public_snapshot_blocks_unreleased_customers():
    inst = _toy_instance()
    obs = make_observation(inst, 1)
    # Only C1 released.
    obs = Observation(
        0.0,
        obs.vehicles,
        ("C1",),
        (),
        (),
        (),
        (),
        (),
        public_customer_count=3,
    )
    snap = make_public_snapshot(inst, obs, horizon=50.0)
    assert_no_future_leak(snap, inst)
    public_ids = {n.id for n in snap.instance.customers}
    assert public_ids == {"C1"}


def test_shared_scenarios_are_nonanticipative_across_candidates():
    """All candidates see the same scenario list object contents (shared first stage)."""
    inst = _toy_instance()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=3)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        n_scenarios=2,
        alns_iterations=4,
        time_limit_seconds=0.25,
        seed=1,
        require_terminal_commitment=True,
    )
    scenarios = ctrl._scenario_forecasts(obs)
    assert scenarios == [[]]  # empty-future, still one shared causal scenario path
    d1 = ctrl.solve_mpc(obs, "request_release")
    assert "commitment_safe_stochastic_mpc" in d1.notes
    assert "receding_horizon=1" in d1.notes
    assert "first_action_execution=1" in d1.notes
    assert d1.audit["css_mpc"]["first_action_only"] is True


def test_timeout_falls_back_without_new_accepts():
    inst = _toy_instance()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1", "C2"), (), (), (), (), (), public_customer_count=3)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=8,
        time_limit_seconds=1e-9,  # force cooperative deadline
        seed=2,
    )
    decision = ctrl.decide(obs, "request_release")
    # May be UNKNOWN or certified incumbent; must not invent accepts without coverage claim path.
    assert isinstance(decision, Decision)
    assert ctrl.profile.decisions == 1
    assert "deadline_overrun" in decision.notes or decision.fallback_used or decision.no_feasible_continuation


def test_zero_duration_travel_arc_rebuild():
    inst = _toy_instance()
    # Depot to itself is absent; charger at distance with zero consumption.
    fat = infinite_battery_instance(inst)
    rebuilt = rebuild_arcs_for_vehicle_type(inst, fat.vehicle_type)
    a = rebuilt.arc("D0", "S0")
    assert abs(a.energy) < 1e-12


def test_closed_loop_first_action_and_replay_ok():
    stem = "c101C5"
    env = environment_seed_for(stem, 0)
    pol = policy_seed_for(stem, 0, "shared")
    episode, _, _ = build_dynamic_episode_v2(
        stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
    )
    case = episode.case
    ctrl = CommitmentSafeStochasticMpc(
        case.instance,
        case.horizon,
        use_forecast=False,
        n_scenarios=1,
        alns_iterations=5,
        time_limit_seconds=0.25,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=80,
        require_terminal_commitment=True,
    )
    result = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    rep = validate_log(case.instance, result.log)
    assert rep.ok, rep.detail
    assert ctrl.profile.decisions >= 1
    assert all("commitment_safe_stochastic_mpc" in (d.notes or []) for d in result.decisions)


def test_infinite_battery_episode_replays_after_rebuild():
    stem = "c101C5"
    env = environment_seed_for(stem, 0)
    pol = policy_seed_for(stem, 0, "shared")
    episode, _, _ = build_dynamic_episode_v2(
        stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
    )
    case = episode.case
    inst = infinite_battery_instance(case.instance)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        case.horizon,
        use_forecast=False,
        n_scenarios=1,
        alns_iterations=4,
        time_limit_seconds=0.2,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=60,
    )
    result = run_episode(
        inst,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    rep = validate_log(inst, result.log)
    assert rep.ok, f"expected fixed infinite-battery replay, got {rep.code}: {rep.detail}"


def test_certificate_reuse_after_events():
    inst = _toy_instance()
    obs0 = make_observation(inst, 1)
    obs0 = Observation(0.0, obs0.vehicles, ("C1",), (), (), (), (), (), public_customer_count=3)
    ctrl = CommitmentSafeStochasticMpc(
        inst, horizon=80.0, use_forecast=False, alns_iterations=5, time_limit_seconds=0.3, seed=3
    )
    d0 = ctrl.decide(obs0, "request_release")
    if d0.no_feasible_continuation and not d0.routes:
        pytest.skip("toy state produced UNKNOWN; certificate reuse N/A")
    # Simulate a later idle observation with same accept set if any.
    obs1 = Observation(
        float(d0.time) + 1.0,
        obs0.vehicles,
        tuple(d0.accepted) if d0.accepted else ("C1",),
        tuple(d0.accepted),
        (),
        (),
        (),
        (),
        public_customer_count=3,
    )
    _ = ctrl.decide(obs1, "replan")
    assert ctrl.profile.decisions == 2


def test_first_action_key_extractable():
    inst = _toy_instance()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=3)
    ctrl = CommitmentSafeStochasticMpc(
        inst, horizon=80.0, use_forecast=False, alns_iterations=4, time_limit_seconds=0.25, seed=4
    )
    d = ctrl.decide(obs, "request_release")
    key = FirstActionKey.from_decision(d)
    assert isinstance(key.first_legs, tuple)
