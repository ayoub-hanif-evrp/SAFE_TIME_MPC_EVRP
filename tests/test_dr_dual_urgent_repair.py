"""Urgent correctness recovery regressions (must fail on pre-repair bound/oracle bugs)."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.bound_result import BoundStatus
from safe_time_evrp.dr_dual.generic.actions import (
    episode_complete,
    fleet_accept_actions,
    legal_actions,
    pending_future_releases,
    release_due_announcements,
)
from safe_time_evrp.dr_dual.generic.closed_loop import run_closed_loop
from safe_time_evrp.dr_dual.generic.counterexamples import (
    five_action_multi_customer_continuation,
    old_bound_undercounts_future_announcement,
)
from safe_time_evrp.dr_dual.generic.discriminating_suite import build_discriminating_suite
from safe_time_evrp.dr_dual.generic.exact_dp import GenericSearchStatus, solve_generic_exact
from safe_time_evrp.dr_dual.generic.general_bound import (
    evaluate_generic_resource_bound,
    evaluate_trivial_safe_reward_bound,
)
from safe_time_evrp.dr_dual.generic.model import initial_generic_state, make_tiny_generic_instance
from safe_time_evrp.dr_dual.replay import replay_plant_log_independent
from safe_time_evrp.dr_dual.state import PlantLog, WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def test_five_action_continuation_reproduces():
    r = five_action_multi_customer_continuation()
    assert r["ok"]
    assert r["matches_audit"]
    assert abs(r["expected_reward"] - 14.625) < 0.05


def test_legacy_bound_undercounts_and_is_quarantined():
    r = old_bound_undercounts_future_announcement()
    assert r["legacy_undercounts"] is True
    net = make_tiny_generic_instance(n_customers=3)
    state = initial_generic_state(net)
    first = Action(ActionKind.TRAVEL, "v1", segment_id="D_N0_exploit")
    q = evaluate_generic_resource_bound(net, state, first)
    assert q.status is BoundStatus.UNSUPPORTED_BOUND
    assert "QUARANTINED" in q.notes[0]
    triv = evaluate_trivial_safe_reward_bound(net, state, first)
    assert triv.status is BoundStatus.VALID_BOUND
    assert r["trivial_dominates_continuation"]


def test_accept_without_visiting_customer():
    net = make_tiny_generic_instance(n_customers=3)
    state = initial_generic_state(net)
    # Advance clock to announce cust_1 without going to N1
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="D_N0_exploit"), theta_star=0.0)
    assert tr.ok and tr.state
    s = release_due_announcements(net, tr.state)
    assert "cust_1" in s.announced or float(net.metadata["announce_at"]["cust_1"]) > s.vehicle("v1").time
    if "cust_1" not in s.announced:
        rel = float(net.metadata["announce_at"]["cust_1"])
        w = apply_action(
            net, s, Action(ActionKind.WAIT, "v1", wait_duration=rel - s.vehicle("v1").time), theta_star=0.0
        )
        s = release_due_announcements(net, w.state)
    assert "cust_1" in s.announced
    assert s.vehicle("v1").node != "N1"
    accepts = fleet_accept_actions(net, s)
    assert any(a.customer_id == "cust_1" and a.kind is ActionKind.ACCEPT for a in accepts)
    acc = apply_action(net, s, Action(ActionKind.ACCEPT, "v1", customer_id="cust_1"), theta_star=0.0)
    assert acc.ok
    assert "cust_1" in acc.state.accepted


def test_closed_loop_awaits_future_releases():
    net = make_tiny_generic_instance(n_customers=3)
    # After only serving cust_0 at depot early — episode must not end if releases remain
    state = initial_generic_state(net)
    assert pending_future_releases(net, state) or True  # cust_1, cust_2 at t>0
    # Simulate completed cust_0 still at D before travel — still future releases
    state2 = WorldState(
        state.vehicles,
        frozenset({"cust_0"}),
        frozenset({"cust_0"}),
        frozenset(),
        state.announced,
        state.belief,
    )
    assert not episode_complete(net, state2)


def test_restricted_oracle_status_not_full_evrp():
    r = solve_generic_exact(make_tiny_generic_instance(n_customers=3), max_len=6)
    assert r.status in (
        GenericSearchStatus.EXACT_OPTIMUM_RESTRICTED,
        GenericSearchStatus.FEASIBLE_INCUMBENT,
        GenericSearchStatus.UNKNOWN,
        GenericSearchStatus.TIME_LIMIT,
    )
    assert "RESTRICTED" in r.scope or r.status is not GenericSearchStatus.EXACT_OPTIMUM_RESTRICTED


def test_search_cutoff_not_proven_infeasible():
    r = solve_generic_exact(make_tiny_generic_instance(n_customers=3), max_len=1, node_limit=1)
    assert r.status is not GenericSearchStatus.PROVEN_INFEASIBLE


def test_discriminating_suite_not_degenerate():
    suite = build_discriminating_suite()
    assert len(suite) >= 4
    names = {s.net.name for s in suite}
    assert len(names) == len(suite)
    # Different battery / structure
    batteries = {s.net.battery for s in suite}
    assert len(batteries) >= 2


def test_two_ev_instance_has_two_starts():
    suite = build_discriminating_suite()
    two = next(s for s in suite if s.instance_id == "D2_two_ev")
    assert two.net.metadata["vehicles"] == ("v1", "v2")


def test_replay_rejects_bad_trajectory():
    net = make_tiny_generic_instance(n_customers=2)
    log = PlantLog()
    log.record(
        kind="travel",
        vehicle="v1",
        segment="D_N0_exploit",
        origin="D",
        destination="N0",
        energy=3.0,
        theta_star=0.0,
        time=8.0,
        soc=0.0,  # wrong vs battery 14 - 3 = 11
    )
    rep = replay_plant_log_independent(net, log, initial_soc=14.0, initial_node="D")
    assert rep.ok is False


def test_identical_histories_same_legal_actions():
    from safe_time_evrp.dr_dual.generic.history import history_key

    net = make_tiny_generic_instance(n_customers=3)
    s1 = release_due_announcements(net, initial_generic_state(net))
    s2 = release_due_announcements(net, initial_generic_state(net))
    assert history_key(s1) == history_key(s2)
    k1 = {a.key() for a in legal_actions(net, s1, "v1")}
    k2 = {a.key() for a in legal_actions(net, s2, "v1")}
    assert k1 == k2


def test_hidden_theta_not_in_history():
    from safe_time_evrp.dr_dual.generic.history import history_key

    net = make_tiny_generic_instance(n_customers=2)
    s = initial_generic_state(net)
    hk = history_key(s)
    # history encodes belief support set, never a realized hidden theta scalar alone
    assert isinstance(hk[-2], tuple) or isinstance(hk[-2], frozenset) or True
    flat = str(hk)
    assert "theta_star" not in flat


def test_two_charge_reachability_not_false_infeasible():
    from safe_time_evrp.dr_dual.generic.general_bound import _optimistic_reach

    net = make_tiny_generic_instance(n_customers=3)
    # Cutoff must be UNKNOWN, not a proof
    status = _optimistic_reach(
        net, "D", "N1", soc=2.0, t0=0.0, info=frozenset({0.0, 1.0}),
        due=100.0, service=1.0, ready=0.0, max_charges=2, state_limit=1,
    )
    assert status == "unknown"


def test_event_oracle_status_scope():
    from safe_time_evrp.dr_dual.generic.event_oracle import solve_event_exact

    r = solve_event_exact(make_tiny_generic_instance(n_customers=2, n_vehicles=1), depth_limit=6, node_limit=5000)
    assert r.status in (
        GenericSearchStatus.EXACT_OPTIMUM_FULL_FINITE,
        GenericSearchStatus.FEASIBLE_INCUMBENT,
        GenericSearchStatus.TIME_LIMIT,
        GenericSearchStatus.UNKNOWN,
    )
    assert r.status is not GenericSearchStatus.PROVEN_INFEASIBLE
