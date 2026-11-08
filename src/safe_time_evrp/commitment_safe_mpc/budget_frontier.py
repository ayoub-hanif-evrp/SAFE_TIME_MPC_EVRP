"""Priority-7 fixed-budget computation–service frontier study.

Matched Insertion / B0 / B1 / M1 (+ ablations) on 10/20/30/50-customer frontier
cases under several cooperative time budgets, with repeated seeds.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_compare import (
    charged_energy_and_time,
    executed_distance_from_log,
)
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_frontier_suite
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.route_resource_profile import EvalMode
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.validation.replay import validate_log

DEFAULT_BUDGETS = (0.05, 0.15, 0.40)
DEFAULT_SEEDS = (3, 7, 11)
# Cap ALNS iterations so the cooperative deadline is the binding resource.
DEFAULT_ITERATIONS = 80


def _controller_factory(name: str, case: BaselineCase, *, budget: float, seed: int, iterations: int):
    if name == "insertion":
        return EventTriggeredMPC(case.instance, case.horizon)
    if name == "b0":
        return ReactiveAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
        )
    if name == "b1":
        return FullValidationAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
        )
    if name == "m1":
        return CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
            eval_mode=EvalMode.INCREMENTAL_EVALUATION,
            reuse_certificates=True,
        )
    if name == "m1_no_reuse":
        return CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
            eval_mode=EvalMode.INCREMENTAL_EVALUATION,
            reuse_certificates=False,
        )
    if name == "m1_full_eval":
        return CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
            eval_mode=EvalMode.FULL_EVALUATION,
            reuse_certificates=True,
        )
    if name == "m1_both_off":
        return CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=iterations,
            time_limit_seconds=budget,
            seed=seed,
            eval_mode=EvalMode.FULL_EVALUATION,
            reuse_certificates=False,
        )
    raise ValueError(f"unknown controller {name}")


def _aggregate_eval_stats(result) -> dict:
    evaluate_route_calls = 0
    full_calls_avoided = 0
    prefix_visits_reused = 0
    suffix_visits_recomputed = 0
    route_evaluations = 0
    iterations = 0
    rescued = 0
    validation_seconds = 0.0
    for d in result.decisions:
        audit = d.audit or {}
        alns = audit.get("alns") or {}
        route_evaluations += int(alns.get("route_evaluations") or 0)
        iterations += int(alns.get("iterations") or 0)
        rescued += len(alns.get("rescued_customers") or [])
        validation_seconds += float(
            audit.get("validation_seconds_this_decision")
            if audit.get("validation_seconds_this_decision") is not None
            else audit.get("validation_seconds") or 0.0
        )
        stats = alns.get("eval_stats") or {}
        evaluate_route_calls += int(stats.get("evaluate_route_calls") or 0)
        full_calls_avoided += int(stats.get("full_calls_avoided") or 0)
        prefix_visits_reused += int(stats.get("prefix_visits_reused") or 0)
        suffix_visits_recomputed += int(stats.get("suffix_visits_recomputed") or 0)
    return {
        "route_evaluations": route_evaluations,
        "alns_iterations": iterations,
        "rescued_customers": rescued,
        "validation_seconds": validation_seconds,
        "evaluate_route_calls": evaluate_route_calls,
        "full_calls_avoided": full_calls_avoided,
        "prefix_visits_reused": prefix_visits_reused,
        "suffix_visits_recomputed": suffix_visits_recomputed,
    }


def run_one(
    case: BaselineCase,
    controller_name: str,
    *,
    budget: float,
    seed: int,
    iterations: int,
) -> dict:
    ctrl = _controller_factory(controller_name, case, budget=budget, seed=seed, iterations=iterations)
    wall0 = perf_counter()
    result = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    wall = perf_counter() - wall0
    report = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = [cid for cid, st in final.items() if st == "completed"]
    accepted_unfulfilled = [cid for cid, st in final.items() if st == "accepted_unfulfilled"]
    rejected = [cid for cid, st in final.items() if st == "rejected"]
    ch_e, ch_t = charged_energy_and_time(result.log)
    charge_starts = sum(1 for r in result.log if r.kind == "charge_start")
    row = {
        "controller": controller_name,
        "case_id": case.case_id,
        "n_customers": len(case.instance.customers),
        "fleet_size": case.fleet_size,
        "budget_seconds": budget,
        "seed": seed,
        "completed_count": len(completed),
        "completed": completed,
        "accepted_unfulfilled_count": len(accepted_unfulfilled),
        "rejected_count": len(rejected),
        "executed_distance": executed_distance_from_log(case.instance, result.log),
        "charged_energy": ch_e,
        "executed_charge_time": ch_t,
        "n_charge_starts": charge_starts,
        "n_replans": len(result.decisions),
        "optimize_seconds": result.optimize_seconds,
        "wall_seconds": wall,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "replay_ok": report.ok,
        "commitment_violations": len(accepted_unfulfilled),
    }
    row.update(_aggregate_eval_stats(result))
    return row


CONTROLLERS = ("insertion", "b0", "b1", "m1", "m1_no_reuse", "m1_full_eval", "m1_both_off")


def run_frontier_study(
    *,
    budgets: tuple[float, ...] = DEFAULT_BUDGETS,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    iterations: int = DEFAULT_ITERATIONS,
    controllers: tuple[str, ...] = CONTROLLERS,
    max_customers: int | None = None,
) -> dict:
    cases = build_frontier_suite()
    if max_customers is not None:
        cases = [c for c in cases if len(c.instance.customers) <= max_customers or c.case_id == "B_rescue_pack"]
    rows: list[dict] = []
    planned = 0
    for case in cases:
        for budget in budgets:
            for seed in seeds:
                for name in controllers:
                    if name == "insertion" and budget != budgets[0]:
                        continue
                    planned += 1
    done = 0
    for case in cases:
        for budget in budgets:
            for seed in seeds:
                for name in controllers:
                    # Insertion ignores budget; still run once per seed for paired streams
                    if name == "insertion" and budget != budgets[0]:
                        continue
                    print(
                        f"[frontier {done + 1}/{planned}] {case.case_id} {name} "
                        f"budget={budget} seed={seed}",
                        flush=True,
                    )
                    rows.append(
                        run_one(case, name, budget=budget, seed=seed, iterations=iterations)
                    )
                    done += 1

    # Aggregate means per (case, controller, budget)
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["case_id"], row["controller"], row["budget_seconds"])
        groups.setdefault(key, []).append(row)

    summary_rows = []
    for (case_id, controller, budget), group in sorted(groups.items()):
        completed = [r["completed_count"] for r in group]
        opt = [r["optimize_seconds"] for r in group]
        dist = [r["executed_distance"] for r in group]
        avoided = [r["full_calls_avoided"] for r in group]
        summary_rows.append(
            {
                "case_id": case_id,
                "controller": controller,
                "budget_seconds": budget,
                "n_seeds": len(group),
                "mean_completed": mean(completed),
                "std_completed": pstdev(completed) if len(completed) > 1 else 0.0,
                "mean_optimize_seconds": mean(opt),
                "std_optimize_seconds": pstdev(opt) if len(opt) > 1 else 0.0,
                "mean_executed_distance": mean(dist),
                "mean_full_calls_avoided": mean(avoided),
                "replay_ok_all": all(r["replay_ok"] for r in group),
                "mean_commitment_violations": mean(r["commitment_violations"] for r in group),
            }
        )

    # Head-to-head: does M1 beat B1 on completed at same budget (mean over seeds)?
    comparisons = []
    for case in cases:
        for budget in budgets:
            b1 = next(
                (
                    s
                    for s in summary_rows
                    if s["case_id"] == case.case_id and s["controller"] == "b1" and s["budget_seconds"] == budget
                ),
                None,
            )
            m1 = next(
                (
                    s
                    for s in summary_rows
                    if s["case_id"] == case.case_id and s["controller"] == "m1" and s["budget_seconds"] == budget
                ),
                None,
            )
            if b1 and m1:
                comparisons.append(
                    {
                        "case_id": case.case_id,
                        "budget_seconds": budget,
                        "m1_minus_b1_completed": m1["mean_completed"] - b1["mean_completed"],
                        "m1_minus_b1_optimize": m1["mean_optimize_seconds"] - b1["mean_optimize_seconds"],
                        "m1_faster": m1["mean_optimize_seconds"] + 1e-9 < b1["mean_optimize_seconds"],
                        "m1_more_service": m1["mean_completed"] > b1["mean_completed"] + 1e-9,
                    }
                )

    return {
        "config": {
            "budgets": list(budgets),
            "seeds": list(seeds),
            "iterations": iterations,
            "controllers": list(controllers),
        },
        "rows": rows,
        "summary_rows": summary_rows,
        "m1_vs_b1": comparisons,
        "headline": {
            "n_raw_runs": len(rows),
            "n_summary_cells": len(summary_rows),
            "m1_service_wins": sum(1 for c in comparisons if c["m1_more_service"]),
            "m1_faster_cells": sum(1 for c in comparisons if c["m1_faster"]),
            "m1_vs_b1_cells": len(comparisons),
            "note": "Service win = higher mean completed at same budget; faster = lower mean optimize_seconds.",
        },
    }


def write_frontier_artifacts(out_dir: Path, **kwargs) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_frontier_study(**kwargs)
    (out_dir / "budget_frontier.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    import sys

    # Default: full frontier. Use --quick for CI-friendly subset (≤20 cust, 2 seeds, 2 budgets).
    quick = "--quick" in sys.argv
    if quick:
        art = write_frontier_artifacts(
            Path("docs/commitment_safe_mpc"),
            budgets=(0.05, 0.15),
            seeds=(7, 11),
            iterations=40,
            max_customers=20,
        )
    else:
        art = write_frontier_artifacts(Path("docs/commitment_safe_mpc"))
    print(json.dumps(art["headline"], indent=2))
    for row in art["m1_vs_b1"]:
        print(
            row["case_id"],
            "budget",
            row["budget_seconds"],
            "d_completed",
            round(row["m1_minus_b1_completed"], 3),
            "d_opt",
            round(row["m1_minus_b1_optimize"], 4),
            "faster",
            row["m1_faster"],
            "more_service",
            row["m1_more_service"],
        )
