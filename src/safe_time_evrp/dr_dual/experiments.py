"""Matched small-instance experiments for decision-relevant dual MPC."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.dr_dual.bounds import bound_dominates_true_q, evaluate_bound
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _first_travel_actions_single,
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.solver import (
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_robust_no_learning,
)


def run_bound_validity_table() -> list[dict]:
    net = make_single_ev_corridors()
    state = initial_state_single(net)
    exact = solve_exact("single")
    rows = []
    for a in _first_travel_actions_single(net, state):
        b = evaluate_bound(net, state, a)
        true_q = _bayes_value_after_first(net, state, a, mode="safe_dual")
        if b is None or true_q is None:
            rows.append({"action": a.key(), "status": "unsafe_or_infeasible"})
            continue
        rows.append(
            {
                "action": a.key(),
                "q_bar": b.q_bar,
                "true_q": true_q,
                "bound_valid": bound_dominates_true_q(b.q_bar, true_q),
                "zero_voi": b.zero_voi_certificate,
                "gap_q_bar_minus_true": b.q_bar - true_q,
            }
        )
    rows.append({"exact_optimum_first": exact.first_action_key, "exact_value": exact.value})
    return rows


def run_pruning_ablation() -> dict:
    with_p = solve_dr_dual(use_pruning=True)
    no_p = solve_dr_dual(use_pruning=False)
    exact = solve_exact("single")
    return {
        "with_pruning": {
            "selected": with_p.selected_action,
            "value": with_p.selected_value,
            "expanded": with_p.actions_expanded,
            "pruned": with_p.actions_pruned_by_bound,
            "safety_out": with_p.actions_ruled_out_by_safety,
            "seconds": with_p.solver_seconds,
            "notes": with_p.notes,
        },
        "no_pruning": {
            "selected": no_p.selected_action,
            "value": no_p.selected_value,
            "expanded": no_p.actions_expanded,
            "pruned": no_p.actions_pruned_by_bound,
            "seconds": no_p.solver_seconds,
        },
        "exact_first": exact.first_action_key,
        "exact_value": exact.value,
        "retains_optimum": with_p.selected_action == exact.first_action_key,
        "fewer_expansions": with_p.actions_expanded < no_p.actions_expanded,
    }


def run_baseline_comparison() -> dict:
    exact = solve_exact("single")
    dual_p = solve_dr_dual(use_pruning=True)
    dual_np = solve_dr_dual(use_pruning=False)
    robust = solve_robust_no_learning()
    info = solve_info_gain_heuristic()
    two = solve_exact("two")
    return {
        "single_ev": {
            "exact": {"first": exact.first_action_key, "value": exact.value, "extras": exact.extras},
            "dr_dual_pruning": {
                "first": dual_p.selected_action,
                "value": dual_p.selected_value,
                "expanded": dual_p.actions_expanded,
                "pruned": dual_p.actions_pruned_by_bound,
            },
            "dr_dual_no_pruning": {
                "first": dual_np.selected_action,
                "value": dual_np.selected_value,
                "expanded": dual_np.actions_expanded,
            },
            "robust": {"first": robust.selected_action, "value": robust.selected_value},
            "info_gain_heuristic": {"first": info.selected_action, "value": info.selected_value},
        },
        "two_ev": {
            "status": two.status.value,
            "first": two.first_action_key,
            "value": two.value,
            "cross_vehicle": two.extras.get("cross_vehicle_info_changes_decision"),
            "details": two.extras.get("details"),
        },
    }


def write_artifacts(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "bound_validity": run_bound_validity_table(),
        "pruning_ablation": run_pruning_ablation(),
        "baselines": run_baseline_comparison(),
    }
    (out_dir / "small_instance_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_artifacts(Path("docs/decision_relevant_dual_mpc"))
    print(json.dumps(art["pruning_ablation"], indent=2))
    print(json.dumps(art["baselines"]["two_ev"], indent=2))
