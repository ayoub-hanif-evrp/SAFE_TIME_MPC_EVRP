"""Decision-relevant dual MPC tests."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.exact_oracle import (
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.experiments import run_bound_validity_table, run_pruning_ablation
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def test_charging_is_explicit_action():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # Travel exploit then serve A then go to charger and charge
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"), theta_star=0.0)
    assert tr.ok and tr.state
    tr = apply_action(net, tr.state, Action(ActionKind.SERVE, "v1", customer_id="cust_A"), theta_star=0.0)
    assert tr.ok and tr.state
    tr = apply_action(net, tr.state, Action(ActionKind.TRAVEL, "v1", segment_id="AS"), theta_star=0.0)
    assert tr.ok and tr.state
    tr = apply_action(net, tr.state, Action(ActionKind.CHARGE_FULL, "v1", charger_id="chg_S"), theta_star=0.0)
    assert tr.ok and tr.state
    assert abs(tr.state.vehicle("v1").soc - net.battery) < 1e-9
    assert tr.state.vehicle("v1").time > state.vehicle("v1").time


def test_alternative_corridors_are_distinct_segments():
    net = make_single_ev_corridors()
    ids = {s.segment_id for s in net.segments_from("D")}
    assert "DA_exploit" in ids and "DA_inform" in ids
    assert net.segments_from("D")[0].segment_id != net.segments_from("D")[1].segment_id


def test_model_inconsistency_fails_safe():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # Noise keeps SOC feasible but matches no theta (exploit predicts energy 4 for all theta).
    tr = apply_action(
        net,
        state,
        Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit"),
        theta_star=0.0,
        noise=1.0,
        noise_tol=0.0,
    )
    assert not tr.ok
    assert tr.model_inconsistent


def test_exact_single_selects_inform():
    r = solve_exact("single")
    assert r.status.value == "EXACT_OPTIMUM"
    assert r.first_action_key is not None
    assert "DA_inform" in r.first_action_key
    assert r.extras["dual_differs_from_passive"]


def test_bounds_are_valid_upper_bounds():
    rows = run_bound_validity_table()
    for row in rows:
        if "bound_valid" in row:
            assert row["bound_valid"] is True


def test_pruning_retains_optimum_and_can_reduce_expansions():
    abl = run_pruning_ablation()
    assert abl["retains_optimum"]
    assert abl["with_pruning"]["expanded"] <= abl["no_pruning"]["expanded"]
    # With useless informative decoy, expect at least one prune
    assert abl["with_pruning"]["pruned"] >= 1
    assert abl["fewer_expansions"]


def test_nonzero_noise_still_updates_or_fails_safe():
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    # Small noise within tol
    tr = apply_action(
        net,
        state,
        Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform"),
        theta_star=1.0,
        noise=0.01,
        noise_tol=0.05,
    )
    assert tr.ok and tr.state is not None
    assert isinstance(tr.state.belief, DiscreteBelief)


def test_two_ev_oracle_runs():
    r = solve_exact("two")
    assert r.status.value in {"EXACT_OPTIMUM", "UNKNOWN"}
    assert r.nodes_expanded > 0
