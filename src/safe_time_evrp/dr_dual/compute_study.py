"""Preregistered computational comparison across structurally varied instances."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from safe_time_evrp.dr_dual.bounds import evaluate_resource_bound
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _first_travel_actions_single,
    initial_state_single,
    solve_exact,
)
from safe_time_evrp.dr_dual.fleet_voi import (
    decompose_legacy_zero_voi,
    make_two_ev_positive_voi,
    measure_fleet_information_value,
)
from safe_time_evrp.dr_dual.instance_suite import build_preregistered_suite
from safe_time_evrp.dr_dual.observation_timing import otub_vs_clairvoyant_on_action
from safe_time_evrp.dr_dual.solver import (
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_passive_mpc,
    solve_robust_mpc,
)


def run_bound_gap_table(net) -> list[dict]:
    state = initial_state_single(net)
    rows = []
    for a in _first_travel_actions_single(net, state):
        q = _bayes_value_after_first(net, state, a, mode="safe_dual")
        if q is None:
            continue
        cmp = otub_vs_clairvoyant_on_action(net, state, a)
        q_r = evaluate_resource_bound(net, state, a)
        rows.append(
            {
                **cmp,
                "reub_v1": q_r,
                "reub_gap": None if q_r is None else q_r - q,
                "otub_gap": None if cmp["otub"] is None else cmp["otub"] - q,
                "drub_gap": None if cmp["drub"] is None else cmp["drub"] - q,
            }
        )
    return rows


def run_suite_comparison(*, trials: int = 7) -> dict:
    suite = build_preregistered_suite()
    instance_rows = []
    for inst in suite:
        net = inst.net
        exact = solve_exact("single", net=net)
        unpruned = solve_dr_dual(net, use_pruning=False)
        modes = {
            "clairvoyant": solve_dr_dual(net, use_pruning=True, bound_mode="clairvoyant"),
            "resource": solve_dr_dual(net, use_pruning=True, bound_mode="resource"),
            "otub": solve_dr_dual(net, use_pruning=True, bound_mode="otub"),
            "combined": solve_dr_dual(net, use_pruning=True, bound_mode="combined"),
        }
        timing = {}
        for label, use_p, bmode in (
            ("unpruned", False, "clairvoyant"),
            ("clairvoyant", True, "clairvoyant"),
            ("resource", True, "resource"),
            ("otub", True, "otub"),
            ("combined", True, "combined"),
        ):
            ts = []
            for _ in range(trials):
                t0 = perf_counter()
                solve_dr_dual(net, use_pruning=use_p, bound_mode=bmode)
                ts.append(perf_counter() - t0)
            timing[label] = {"mean_s": mean(ts), "trials": trials}

        robust = solve_robust_mpc(net)
        passive = solve_passive_mpc(net)
        info = solve_info_gain_heuristic(net)
        gaps = run_bound_gap_table(net)

        instance_rows.append(
            {
                "instance_id": inst.instance_id,
                "network": net.name,
                "tags": list(inst.tags),
                "n_first_actions": len(_first_travel_actions_single(net, initial_state_single(net))),
                "exact_first": exact.first_action_key,
                "exact_value": exact.value,
                "unpruned": {
                    "first": unpruned.selected_action,
                    "expanded": unpruned.actions_expanded,
                    "heavy": unpruned.counters.get("total_heavy_calls"),
                    "agrees_exact": unpruned.selected_action == exact.first_action_key,
                },
                "pruning": {
                    k: {
                        "first": v.selected_action,
                        "expanded": v.actions_expanded,
                        "pruned": v.actions_pruned_by_bound,
                        "heavy": v.counters.get("total_heavy_calls"),
                        "agrees_exact": v.selected_action == exact.first_action_key,
                        "pruning_costs_more_heavy_than_unpruned": (
                            (v.counters.get("total_heavy_calls") or 0)
                            > (unpruned.counters.get("total_heavy_calls") or 0)
                        ),
                    }
                    for k, v in modes.items()
                },
                "timing_mean_s": timing,
                "baselines": {
                    "robust_first": robust.selected_action,
                    "passive_first": passive.selected_action,
                    "info_gain_first": info.selected_action,
                    "info_gain_matches_exact": info.selected_action == exact.first_action_key,
                    "dual_differs_from_passive": exact.first_action_key != passive.selected_action,
                    "dual_differs_from_info_gain": exact.first_action_key != info.selected_action,
                },
                "bound_gaps": gaps,
            }
        )

    # Aggregate: when does pruning help?
    help_counts = {k: 0 for k in ("clairvoyant", "resource", "otub", "combined")}
    agree = {k: 0 for k in help_counts}
    n = len(instance_rows)
    for row in instance_rows:
        u_heavy = row["unpruned"]["heavy"] or 0
        for k, v in row["pruning"].items():
            if v["agrees_exact"]:
                agree[k] += 1
            if (v["heavy"] or 0) < u_heavy and v["pruned"] > 0:
                help_counts[k] += 1

    return {
        "instances": instance_rows,
        "summary": {
            "n_instances": n,
            "exact_agreement_counts": agree,
            "heavy_ops_strictly_improved_with_prune": help_counts,
            "note": "Do not claim scalability from millisecond means alone",
        },
    }


def run_fleet_voi_report() -> dict:
    legacy = decompose_legacy_zero_voi()
    pos_net = make_two_ev_positive_voi()
    pos = measure_fleet_information_value(pos_net, ev1_segment="E1_inform")
    return {
        "legacy_zero_voi_decomposition": legacy,
        "positive_voi_network": {
            "network": pos.network,
            "v_shared": pos.v_shared,
            "v_without_sharing": pos.v_without_sharing,
            "delta_voi": pos.delta_voi,
            "shared_policy": pos.shared_policy,
            "no_share_policy": pos.no_share_policy,
            "per_theta_shared": pos.per_theta_shared,
            "per_theta_no_share": pos.per_theta_no_share,
            "notes": list(pos.notes),
            "positive": pos.delta_voi > 1e-9,
        },
    }


def write_generalization_artifacts(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fleet_voi": run_fleet_voi_report(),
        "compute_suite": run_suite_comparison(trials=5),
    }
    (out_dir / "generalization_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_generalization_artifacts(Path("docs/decision_relevant_dual_mpc"))
    print(json.dumps(art["fleet_voi"], indent=2))
    print(json.dumps(art["compute_suite"]["summary"], indent=2))
