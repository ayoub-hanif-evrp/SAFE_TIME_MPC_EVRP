"""Matched small-instance experiments for decision-relevant dual MPC."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.dr_dual.bounds import (
    bound_dominates_true_q,
    charging_makes_old_resource_bound_invalid,
    evaluate_bound,
)
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _first_travel_actions_single,
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.fleet_oracle import reverse_ranking_regression
from safe_time_evrp.dr_dual.network import make_single_ev_corridors
from safe_time_evrp.dr_dual.solver import (
    run_fair_compute_experiment,
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_passive_mpc,
    solve_robust_mpc,
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
                "q_bar_clairvoyant": b.q_bar_clairvoyant,
                "q_bar_resource": b.q_bar_resource,
                "resource_version": b.resource_version,
                "true_q": true_q,
                "clairvoyant_bound_valid": bound_dominates_true_q(b.q_bar_clairvoyant, true_q),
                "resource_bound_valid_vs_true": bound_dominates_true_q(b.q_bar_resource, true_q),
                "bound_valid": bound_dominates_true_q(b.q_bar_clairvoyant, true_q),
                "zero_voi_status": b.zero_voi_status,
                "resource_tighter_than_clairvoyant": b.q_bar_resource + 1e-9 < b.q_bar_clairvoyant,
                "gap_q_bar_minus_true": b.q_bar_clairvoyant - true_q,
            }
        )
    rows.append({"exact_optimum_first": exact.first_action_key, "exact_value": exact.value})
    rows.append({"reub_v0_counterexample": charging_makes_old_resource_bound_invalid()})
    return rows


def run_pruning_ablation() -> dict:
    with_p = solve_dr_dual(use_pruning=True, bound_mode="clairvoyant")
    no_p = solve_dr_dual(use_pruning=False)
    with_r = solve_dr_dual(use_pruning=True, bound_mode="resource")
    exact = solve_exact("single")
    return {
        "with_pruning_clairvoyant": {
            "selected": with_p.selected_action,
            "value": with_p.selected_value,
            "expanded": with_p.actions_expanded,
            "pruned": with_p.actions_pruned_by_bound,
            "safety_out": with_p.actions_ruled_out_by_safety,
            "seconds": with_p.solver_seconds,
            "counters": with_p.counters,
            "incumbent_L": with_p.incumbent_lower_bound,
            "notes": with_p.notes,
        },
        "with_pruning": {
            "selected": with_p.selected_action,
            "value": with_p.selected_value,
            "expanded": with_p.actions_expanded,
            "pruned": with_p.actions_pruned_by_bound,
            "safety_out": with_p.actions_ruled_out_by_safety,
            "seconds": with_p.solver_seconds,
            "counters": with_p.counters,
            "incumbent_L": with_p.incumbent_lower_bound,
            "notes": with_p.notes,
        },
        "with_pruning_resource": {
            "selected": with_r.selected_action,
            "value": with_r.selected_value,
            "expanded": with_r.actions_expanded,
            "pruned": with_r.actions_pruned_by_bound,
            "counters": with_r.counters,
        },
        "no_pruning": {
            "selected": no_p.selected_action,
            "value": no_p.selected_value,
            "expanded": no_p.actions_expanded,
            "pruned": no_p.actions_pruned_by_bound,
            "seconds": no_p.solver_seconds,
            "counters": no_p.counters,
            "bound_evals": no_p.counters.get("bound_evaluations", 0)
            + no_p.counters.get("resource_bound_evaluations", 0),
        },
        "exact_first": exact.first_action_key,
        "exact_value": exact.value,
        "retains_optimum": with_p.selected_action == exact.first_action_key,
        "fewer_expansions": with_p.actions_expanded < no_p.actions_expanded,
        "unpruned_computes_no_bounds": (
            no_p.counters.get("bound_evaluations", 0) + no_p.counters.get("resource_bound_evaluations", 0) == 0
        ),
        "incumbent_is_executable_policy_value": True,
    }


def run_baseline_comparison() -> dict:
    exact = solve_exact("single")
    dual_p = solve_dr_dual(use_pruning=True)
    dual_np = solve_dr_dual(use_pruning=False)
    robust = solve_robust_mpc()
    passive = solve_passive_mpc()
    info = solve_info_gain_heuristic()
    two = solve_exact("two")
    return {
        "single_ev": {
            "exact_dual": {"first": exact.first_action_key, "value": exact.value, "extras": exact.extras},
            "dr_dual_pruning": {
                "first": dual_p.selected_action,
                "value": dual_p.selected_value,
                "expanded": dual_p.actions_expanded,
                "pruned": dual_p.actions_pruned_by_bound,
            },
            "dr_dual_unpruned": {
                "first": dual_np.selected_action,
                "value": dual_np.selected_value,
                "expanded": dual_np.actions_expanded,
                "bound_evals": dual_np.counters.get("bound_evaluations", 0)
                + dual_np.counters.get("resource_bound_evaluations", 0),
            },
            "robust_mpc": {
                "first": robust.selected_action,
                "selection_score_worst_case": robust.selection_score,
                "true_bayes_value": robust.true_bayes_value,
            },
            "optimized_passive": {
                "first": passive.selected_action,
                "selection_score_passive": passive.selection_score,
                "true_bayes_value": passive.true_bayes_value,
                "matches_exact_passive": passive.selected_action == exact.extras.get("passive_optimized_first"),
            },
            "info_gain_heuristic": {
                "first": info.selected_action,
                "selection_score_abs_phi1": info.selection_score,
                "true_bayes_value": info.true_bayes_value,
            },
        },
        "two_ev": {
            "status": two.status.value,
            "first": two.first_action_key,
            "value": two.value,
            "nonanticipative": two.extras.get("nonanticipative"),
            "cross_vehicle_info_changes_ev1_first_value": two.extras.get("cross_vehicle_info_changes_ev1_first_value"),
            "details": two.extras.get("details"),
            "reverse_ranking_abstract": reverse_ranking_regression(),
        },
        "fair_compute": run_fair_compute_experiment(trials=3),
    }


def write_artifacts(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    from safe_time_evrp.dr_dual.compute_study import write_generalization_artifacts

    payload = {
        "bound_validity": run_bound_validity_table(),
        "pruning_ablation": run_pruning_ablation(),
        "baselines": run_baseline_comparison(),
    }
    (out_dir / "small_instance_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["generalization"] = write_generalization_artifacts(out_dir)
    return payload


if __name__ == "__main__":
    art = write_artifacts(Path("docs/decision_relevant_dual_mpc"))
    print(json.dumps(art["pruning_ablation"], indent=2))
    print(json.dumps(art["generalization"]["compute_suite"]["summary"], indent=2))
