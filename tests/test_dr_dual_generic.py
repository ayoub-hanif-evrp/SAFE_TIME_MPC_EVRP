"""Phase 1–5: bound status, causality, generic EVRP, general bound, adversarial."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.bound_result import BoundStatus
from safe_time_evrp.dr_dual.bounds import evaluate_resource_bound_result
from safe_time_evrp.dr_dual.exact_oracle import initial_state_single
from safe_time_evrp.dr_dual.generic.exact_dp import solve_generic_exact
from safe_time_evrp.dr_dual.generic.general_bound import evaluate_generic_resource_bound
from safe_time_evrp.dr_dual.generic.instance_gen import build_frozen_generic_suite
from safe_time_evrp.dr_dual.generic.model import (
    initial_generic_state,
    make_no_charger_informative,
    make_tiny_generic_instance,
)
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.replay import replay_plant_log_independent
from safe_time_evrp.dr_dual.solver import solve_dr_dual
from safe_time_evrp.dr_dual.state import PlantLog, WorldState
from safe_time_evrp.dr_dual.transition import apply_action


def test_unsupported_resource_bound_does_not_silent_discard():
    net = make_no_charger_informative()
    state = initial_state_single(net)
    a = Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform")
    br = evaluate_resource_bound_result(net, state, a)
    assert br.status is BoundStatus.UNSUPPORTED_BOUND
    stats = solve_dr_dual(net, state=state, use_pruning=True, bound_mode="resource")
    assert any("bound_unavailable_forced_expand" in n for n in stats.notes)
    assert stats.selected_action is not None
    # Must evaluate non-seed actions rather than silently skipping
    assert stats.actions_expanded >= 1


def test_model_inconsistency_commits_physics():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    tr = apply_action(
        net,
        state,
        Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"),
        theta_star=0.0,
        noise=1.0,
        noise_tol=0.0,
    )
    assert tr.state is not None
    assert tr.state.vehicle("v1").node == "A"
    assert tr.model_inconsistent
    assert not tr.ok


def test_receding_horizon_accepts_state_arg():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert tr.ok and tr.state is not None
    # Next decision from carried state (not fresh prior-only cold start API)
    stats = solve_dr_dual(net, state=tr.state, use_pruning=False)
    assert stats.counters is not None


def test_replay_rejects_soc_mismatch():
    net = make_single_ev_corridors()
    log = PlantLog()
    log.record(
        kind="travel",
        vehicle="v1",
        segment="DA_exploit",
        origin="D",
        destination="A",
        energy=4.0,
        theta_star=0.0,
        time=10.0,
        soc=99.0,  # wrong
    )
    rep = replay_plant_log_independent(net, log, initial_soc=12.0, initial_node="D")
    assert rep.ok is False
    assert "soc_mismatch_vs_log" in rep.notes


def test_generic_exact_runs():
    net = make_tiny_generic_instance(n_customers=3, n_vehicles=1)
    r = solve_generic_exact(net, max_len=3)
    assert r.status.value in {
        "EXACT_OPTIMUM_RESTRICTED",
        "EXACT_OPTIMUM_FULL_FINITE",
        "FEASIBLE_INCUMBENT",
        "PROVEN_INFEASIBLE",
        "UNKNOWN",
        "TIME_LIMIT",
    }
    assert r.nodes_expanded >= 1


def test_generic_bound_quarantined_unsupported():
    net = make_tiny_generic_instance(n_customers=3)
    state = initial_generic_state(net)
    from safe_time_evrp.dr_dual.generic.actions import legal_actions
    from safe_time_evrp.dr_dual.generic.general_bound import evaluate_trivial_safe_reward_bound

    acts = [a for a in legal_actions(net, state, "v1") if a.kind.value == "travel"]
    assert acts
    br = evaluate_generic_resource_bound(net, state, acts[0])
    assert br.status is BoundStatus.UNSUPPORTED_BOUND
    triv = evaluate_trivial_safe_reward_bound(net, state, acts[0])
    assert triv.status is BoundStatus.VALID_BOUND


def test_trivial_bound_dominates_when_valid():
    from safe_time_evrp.dr_dual.generic.exact_dp import _bayes_after_first, _first_actions
    from safe_time_evrp.dr_dual.generic.general_bound import evaluate_trivial_safe_reward_bound

    net = make_tiny_generic_instance(n_customers=3)
    state = initial_generic_state(net)
    for a in _first_actions(net, state)[:3]:
        q = _bayes_after_first(net, state, a, noise=0.0, max_len=3)
        br = evaluate_trivial_safe_reward_bound(net, state, a)
        if q is not None and br.status is BoundStatus.VALID_BOUND and br.value is not None:
            assert br.value + 1e-6 >= q


def test_frozen_suite_structurally_varied():
    suite = build_frozen_generic_suite()
    assert len(suite) == 8
    names = {s.net.name for s in suite}
    assert len(names) == 8
    n_cust = {len(s.net.customers) for s in suite}
    assert len(n_cust) >= 2


def test_accept_before_observation():
    net = make_tiny_generic_instance(n_customers=3)
    state = initial_generic_state(net)
    # Announce cust_1 early
    state = WorldState(
        state.vehicles,
        state.accepted,
        state.completed,
        state.rejected,
        state.announced | {"cust_1"},
        state.belief,
        state.stage,
    )
    acc = apply_action(net, state, Action(ActionKind.ACCEPT, "v1", customer_id="cust_1"), theta_star=0.0)
    assert acc.ok
    # Travel still after accept
    tr = apply_action(net, acc.state, Action(ActionKind.TRAVEL, "v1", segment_id="D_N0_inform"), theta_star=0.0)
    assert tr.ok or tr.model_inconsistent


def test_unknown_bound_forces_expand_path():
    # Resource on no-charger: unsupported → forced expand notes
    net = make_no_charger_informative()
    stats = solve_dr_dual(net, use_pruning=True, bound_mode="resource")
    assert any("forced_expand" in n for n in stats.notes)
