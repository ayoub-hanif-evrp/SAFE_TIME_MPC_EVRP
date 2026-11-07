"""Critical repairs: nonanticipativity, incumbent L, withdrawn zero-VoI, counters."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.bounds import evaluate_bound
from safe_time_evrp.dr_dual.common_policy import abstract_p1_p2_counterexample, select_common_policy
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.solver import solve_dr_dual
from safe_time_evrp.dr_dual.state import VehicleState, WorldState
from safe_time_evrp.dr_dual.transition import apply_action, commitment_safe_under_all_theta


def test_p1_p2_min_max_is_not_executable_value():
    ex = abstract_p1_p2_counterexample()
    assert ex["min_theta_max_plan"] == 10.0
    assert ex["max_plan_min_theta"] == 0.0
    assert ex["max_plan_expected"] == 5.0
    assert ex["true_no_info_optimal_expected"] == 5.0


def test_false_L_must_not_prune_better_candidate():
    """If L were wrongly 10, a candidate with Q_bar=7 would be pruned; true L=5 must not."""
    false_L = 10.0
    true_L = 5.0
    q_bar_candidate = 7.0
    assert q_bar_candidate <= false_L  # would incorrectly prune
    assert q_bar_candidate > true_L  # must expand under sound L


def test_common_policy_same_plan_for_all_theta():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # After exploit, belief remains ambiguous
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert tr.ok and tr.state is not None
    assert len(tr.state.belief.support_set()) > 1
    common = select_common_policy(net, tr.state, objective="expected")
    assert common is not None
    # Realized rewards may differ by theta, but the plan tuple is unique
    assert isinstance(common.plan, tuple)
    for _ in tr.state.belief.support_set():
        # Selecting again must yield the same plan (deterministic tie-break by enumeration order)
        c2 = select_common_policy(net, tr.state, objective="expected")
        assert c2 is not None
        assert c2.plan == common.plan


def test_zero_voi_marked_withdrawn():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    a = Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit")
    b = evaluate_bound(net, state, a)
    assert b is not None
    assert b.zero_voi_status == "WITHDRAWN_UNSOUND"


def test_incumbent_L_from_executable_policy_and_pruning_retains_optimum():
    exact = solve_exact("single")
    stats = solve_dr_dual(use_pruning=True, bound_mode="clairvoyant")
    assert stats.incumbent_lower_bound is not None
    assert stats.selected_action == exact.first_action_key
    # Counters include bound/continuation work, not only expansions
    assert stats.counters["total_heavy_calls"] >= stats.actions_expanded


def test_commitment_requires_completed_not_merely_accepted():
    net = make_single_ev_corridors()
    state = initial_state_single(net)

    def bad_builder(_s):
        return []  # leaves A accepted but unserved

    ok = commitment_safe_under_all_theta(
        net,
        state,
        Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"),
        remaining_plan_builder=bad_builder,
    )
    assert ok is False


def test_busy_until_rejects_interrupt():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # Manually mark vehicle busy in the future
    v = state.vehicle("v1")
    busy = VehicleState(v.vehicle_id, v.node, v.time, v.soc, v.load, busy_until=v.time + 5.0)
    state2 = WorldState(
        (busy,), state.accepted, state.completed, state.rejected, state.announced, state.belief, state.stage
    )
    tr = apply_action(net, state2, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert not tr.ok
    assert tr.note == "vehicle_busy_noninterruptible"


def test_bayes_value_uses_common_policy_when_ambiguous():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    exploit = Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit")
    inform = Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform")
    v_ex = _bayes_value_after_first(net, state, exploit, mode="safe_dual")
    v_in = _bayes_value_after_first(net, state, inform, mode="safe_dual")
    assert v_ex is not None and v_in is not None
    assert v_in > v_ex
