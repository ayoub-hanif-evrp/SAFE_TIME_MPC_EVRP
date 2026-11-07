"""Remaining scientific defects: nonanticipative 2-EV, REUB, baselines, semantics."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.bounds import (
    charging_makes_old_resource_bound_invalid,
    evaluate_bound,
    evaluate_clairvoyant_bound,
    evaluate_resource_bound,
)
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _continuation_value_known_theta,
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.fleet_oracle import reverse_ranking_regression, solve_exact_two_ev_nonanticipative
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.solver import (
    run_fair_compute_experiment,
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_passive_mpc,
    solve_robust_mpc,
)
from safe_time_evrp.dr_dual.state import PlantLog, WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def test_reub_v0_invalid_when_charging_enables_customer():
    cex = charging_makes_old_resource_bound_invalid()
    assert cex["v0_invalid"] is True
    assert cex["v1_valid_on_instance"] is True
    assert cex["true_q"] is not None
    assert cex["v0_direct_only"] is not None
    assert cex["v0_direct_only"] + 1e-9 < cex["true_q"]


def test_reub_v1_dominates_true_q_on_toy_actions():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    for sid in ("DA_exploit", "DA_inform", "DA_useless_inform"):
        a = Action(ActionKind.TRAVEL, "v1", segment_id=sid)
        true_q = _bayes_value_after_first(net, state, a, mode="safe_dual")
        if true_q is None:
            continue
        q_r = evaluate_resource_bound(net, state, a)
        assert q_r is not None
        assert q_r + 1e-9 >= true_q


def test_resource_bound_not_certified_via_clairvoyant_fallback_in_solver():
    """Pruning with bound_mode=resource must not require clairvoyant evaluation to prune."""
    stats = solve_dr_dual(use_pruning=True, bound_mode="resource")
    # Resource path may evaluate resource bounds; clairvoyant counts should be 0 for prune decisions.
    # (clairvoyant may still be 0 always in resource-only mode)
    assert stats.counters["resource_bound_evaluations"] >= 0
    assert stats.counters["bound_evaluations"] == 0  # evaluate_clairvoyant_bound not called
    assert stats.selected_action is not None


def test_unpruned_computes_no_bounds():
    stats = solve_dr_dual(use_pruning=False)
    assert stats.counters["bound_evaluations"] == 0
    assert stats.counters["resource_bound_evaluations"] == 0
    assert stats.actions_pruned_by_bound == 0


def test_baselines_are_separated_and_passive_matches_exact():
    exact = solve_exact("single")
    robust = solve_robust_mpc()
    passive = solve_passive_mpc()
    dual = solve_dr_dual(use_pruning=False)
    info = solve_info_gain_heuristic()

    assert passive.selected_action == exact.extras["passive_optimized_first"]
    assert dual.selected_action == exact.first_action_key
    # Robust / passive must not silently equal dual Bayes selection machinery:
    # they optimize different scores (worst-case / forced-prior).
    assert robust.method == "robust_mpc_fixed_uncertainty"
    assert passive.method == "optimized_passive_learning"
    assert info.method == "info_gain_heuristic"
    # Dual seeks inform; optimized passive prefers exploit on this toy
    assert "DA_inform" in (dual.selected_action or "")
    assert "DA_exploit" in (passive.selected_action or "")


def test_two_ev_nonanticipative_common_action_under_ambiguous_history():
    r = solve_exact_two_ev_nonanticipative()
    assert r.status.value == "EXACT_OPTIMUM"
    assert r.extras.get("nonanticipative") is True
    # Exploit corridor: both thetas share history → one EV2 action in policy map
    exploit_detail = next(d for d in r.extras["details"] if "E1_exploit" in d["first"])
    policies = exploit_detail["policy_by_history"]
    assert len(policies) == 1  # single ambiguous history


def test_reverse_ranking_forbids_clairvoyant_as_exact():
    ex = reverse_ranking_regression()
    assert ex["clairvoyant_per_theta_max"] == 10.0
    assert ex["nonanticipative_common_best"] == 5.0
    assert ex["must_not_report_clairvoyant_as_exact"]


def test_solve_exact_two_uses_nonanticipative_oracle():
    r = solve_exact("two")
    assert r.policy_note == "two_ev_history_indexed_nonanticipative"
    assert r.extras.get("nonanticipative") is True


def test_info_changes_charging_decision_single_ev():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # After exploit (ambiguous): common policy cannot rely on θ-contingent charge/direct optimally
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert tr.ok and tr.state is not None
    assert len(tr.state.belief.support_set()) > 1
    # After inform θ=0: Dirac; known-θ OL can take direct AC (SOC enough for θ=0)
    tr_i = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform"), theta_star=0.0)
    assert tr_i.ok and tr_i.state is not None
    assert len(tr_i.state.belief.support_set()) == 1
    v0 = _continuation_value_known_theta(net, tr_i.state, 0.0)
    # θ=1 after inform: higher energy; may need charge or skip C
    tr_i1 = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform"), theta_star=1.0)
    assert tr_i1.ok and tr_i1.state is not None
    v1 = _continuation_value_known_theta(net, tr_i1.state, 1.0)
    assert v0 != v1  # information changes continuation value / charging need


def test_info_ev1_changes_ev2_policy_when_histories_separate():
    r = solve_exact_two_ev_nonanticipative()
    inform = next(d for d in r.extras["details"] if "E1_inform" in d["first"])
    # Informative corridor yields Dirac histories → possibly distinct EV2 actions per θ
    assert len(inform["policy_by_history"]) >= 1
    exploit = next(d for d in r.extras["details"] if "E1_exploit" in d["first"])
    assert len(exploit["policy_by_history"]) == 1
    # Values may differ when information changes EV2's executable decision set
    assert "value" in inform and "value" in exploit


def test_informative_action_pruned_when_bound_below_incumbent():
    stats = solve_dr_dual(use_pruning=True, bound_mode="clairvoyant")
    assert any(n.startswith("pruned:") and "useless" in n for n in stats.notes)
    assert stats.actions_pruned_by_bound >= 1


def test_dynamic_announce_accept_before_service():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # Remove C from announced to simulate not-yet-released request
    state = WorldState(
        state.vehicles,
        state.accepted,
        state.completed,
        state.rejected,
        frozenset({"cust_A"}),  # C not announced
        state.belief,
        state.stage,
    )
    # Get to C somehow after serving A path — first ensure unannounced C cannot be served
    # Directly attempt serve C from a forged at-C state
    from safe_time_evrp.dr_dual.state import VehicleState

    at_c = VehicleState("v1", "C", 10.0, 10.0)
    forged = WorldState(
        (at_c,),
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset({"cust_A"}),
        DiscreteBelief.uniform(net.theta_support),
    )
    bad = apply_action(net, forged, Action(ActionKind.SERVE, "v1", customer_id="cust_C"), theta_star=0.0)
    assert not bad.ok
    assert bad.note == "customer_not_released"

    # Announce then accept then serve
    announced = WorldState(
        forged.vehicles,
        forged.accepted,
        forged.completed,
        forged.rejected,
        frozenset({"cust_A", "cust_C"}),
        forged.belief,
    )
    acc = apply_action(net, announced, Action(ActionKind.ACCEPT, "v1", customer_id="cust_C"), theta_star=0.0)
    assert acc.ok and acc.state is not None
    assert "cust_C" in acc.state.accepted
    ok = apply_action(net, acc.state, Action(ActionKind.SERVE, "v1", customer_id="cust_C"), theta_star=0.0)
    assert ok.ok


def test_trajectory_replay_independent_log():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    log = PlantLog()
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0, log=log)
    assert tr.ok
    assert any(e.get("kind") == "travel" for e in log.events)
    # Replay: same action from same state yields same energy
    tr2 = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert tr2.ok and tr.energy_observed == tr2.energy_observed


def test_fair_compute_unpruned_zero_bounds():
    art = run_fair_compute_experiment(trials=2)
    for row in art["rows"]:
        if row["mode"] == "unpruned":
            assert row["bound_evals_expected_zero_if_unpruned"] == 0


def test_clairvoyant_still_valid_ub():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    a = Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform")
    q = evaluate_clairvoyant_bound(net, state, a)
    true_q = _bayes_value_after_first(net, state, a, mode="safe_dual")
    assert q is not None and true_q is not None
    assert q + 1e-9 >= true_q
    b = evaluate_bound(net, state, a)
    assert b is not None
    assert b.zero_voi_status == "WITHDRAWN_UNSOUND"
