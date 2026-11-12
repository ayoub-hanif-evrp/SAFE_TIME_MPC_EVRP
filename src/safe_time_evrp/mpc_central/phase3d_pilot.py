"""Phase 3D development pilot: repaired plant + closed-loop predictive MPC.

Modest matched comparisons only. Holdout untouched. No large benchmarks.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.mpc_central.causal_plant import expected_action_value
from safe_time_evrp.mpc_central.decision_regret import (
    adaptive_mpc,
    equal_allocation,
    paired_common_random,
    run_fairness_suite,
    uniform_rollout,
)
from safe_time_evrp.mpc_central.eval_bank import OfflineOracle
from safe_time_evrp.mpc_central.forks import all_forks
from safe_time_evrp.mpc_central.fulfillment_audit import audit_frontier_unfulfilled
from safe_time_evrp.mpc_central.phase3d_splits import (
    development_cases,
    fit_train_forecast,
    holdout_cases,
    split_manifest,
)
from safe_time_evrp.validation.replay import validate_log


def repaired_fork_action_values() -> dict:
    """Regenerate exhaustive first-action values under B1 recourse + arc distance."""
    cases = []
    for spec in all_forks():
        row = {"case_id": spec.case_id, "actions": {}}
        for action in spec.candidate_actions:
            exp, scores = expected_action_value(spec, action)
            row["actions"][action] = {
                "expected_value": exp,
                "scenarios": [
                    {
                        "value": s.value,
                        "completed": list(s.completed),
                        "accepted_unfulfilled": list(s.accepted_unfulfilled),
                        "executed_distance": next(
                            (float(n.split("=", 1)[1]) for n in s.notes if n.startswith("executed_distance=")),
                            0.0,
                        ),
                        "replay_ok": s.replay_ok,
                        "recourse": next((n for n in s.notes if n.startswith("recourse=")), "recourse=?"),
                    }
                    for s in scores
                ],
            }
        best = max(row["actions"], key=lambda a: row["actions"][a]["expected_value"])
        row["best_action"] = best
        cases.append(row)
    return {"cases": cases, "scoring": "SERVICE*completed - 250*AU - 1*executed_distance", "recourse": "b1_validated"}


def decision_layer_pilot(*, budgets: tuple[int, ...] = (3, 4)) -> dict:
    fairness = run_fairness_suite(budgets=budgets, reverse_actions=True, reverse_scenarios=True)
    head_to_head = []
    for spec in all_forks():
        oracle = OfflineOracle.build(spec)
        for b in budgets:
            b_eff = max(b, len(spec.candidate_actions))
            uni = uniform_rollout(spec, oracle, budget=b_eff)
            ada = adaptive_mpc(spec, oracle, budget=b_eff)
            eq = equal_allocation(spec, oracle, budget=b_eff)
            crn = paired_common_random(spec, oracle, budget=b_eff)
            head_to_head.append(
                {
                    "case_id": spec.case_id,
                    "budget": b_eff,
                    "uniform_regret": uni.regret,
                    "adaptive_regret": ada.regret,
                    "equal_regret": eq.regret,
                    "crn_regret": crn.regret,
                    "uniform_action": uni.action,
                    "adaptive_action": ada.action,
                    "equal_action": eq.action,
                    "crn_action": crn.action,
                }
            )
    return {"fairness": fairness, "head_to_head_base": head_to_head}


def _summarize_episode(case, name: str, result) -> dict:
    report = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sorted(cid for cid, st in final.items() if st == "completed")
    au = sorted(cid for cid, st in final.items() if st == "accepted_unfulfilled")
    rejected = sorted(cid for cid, st in final.items() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
    charge_starts = sum(1 for rec in result.log if rec.kind == "charge_start")
    first_actions = []
    for d in result.decisions[:3]:
        first_actions.append(
            {
                "trigger": d.trigger,
                "newly_accepted": list(d.newly_accepted),
                "planned_service": list(d.planned_service)[:6],
                "notes": list(d.notes)[:5],
            }
        )
    overrun = sum(1 for d in result.decisions if (d.audit or {}).get("predictive_mpc", {}).get("deadline_overrun"))
    causal = sum(1 for d in result.decisions if "causal_rollouts=1" in (d.notes or []))
    return {
        "controller": name,
        "completed_count": len(completed),
        "accepted_unfulfilled_count": len(au),
        "rejected_count": len(rejected),
        "executed_distance": dist,
        "charge_starts": charge_starts,
        "optimize_seconds": result.optimize_seconds,
        "fallback_count": result.fallback_count,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "termination_reason": result.termination_reason,
        "replay_ok": report.ok,
        "deadline_overruns": overrun,
        "causal_rollout_decisions": causal,
        "first_decisions": first_actions,
        "completed": completed,
        "accepted_unfulfilled": au,
    }


def closed_loop_pilot(*, alns_iterations: int = 12, alns_time: float = 0.35, seed: int = 7) -> dict:
    """Matched closed-loop on development cases; forecast fitted on train only."""
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed)
    cases = development_cases()
    holdout_ids = [c.case_id for c in holdout_cases()]
    rows = []
    for case in cases:
        controllers = {
            "insertion": EventTriggeredMPC(case.instance, case.horizon),
            "b1": FullValidationAlnsMpc(
                case.instance,
                case.horizon,
                iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed,
            ),
            "m1": CertificateCarryingAlnsMpc(
                case.instance,
                case.horizon,
                iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed,
            ),
            "predictive_uniform": CommitmentSafePredictiveMpc(
                case.instance,
                case.horizon,
                forecast=forecast,
                n_scenarios=2,
                alns_iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed,
                allocation="uniform",
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=250,
            ),
            "predictive_paired_crn": CommitmentSafePredictiveMpc(
                case.instance,
                case.horizon,
                forecast=forecast,
                n_scenarios=2,
                alns_iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed + 1,
                allocation="paired_crn",
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=250,
            ),
        }
        case_row = {
            "case_id": case.case_id,
            "fleet_size": case.fleet_size,
            "split": "development",
            "forecast_source": "train_only",
            "controllers": {},
        }
        for name, ctrl in controllers.items():
            res = run_episode(
                case.instance,
                case.releases,
                fleet_size=case.fleet_size,
                horizon=case.horizon,
                max_replan_interval=case.max_replan_interval,
                t_max=case.t_max,
                controller=ctrl,
            )
            case_row["controllers"][name] = _summarize_episode(case, name, res)
        rows.append(case_row)
    return {
        "n_cases": len(rows),
        "split": split_manifest(),
        "holdout_untouched": holdout_ids,
        "forecast_model_id": forecast.model_id,
        "rows": rows,
    }


def run_au_residual_audit(*, iterations: int = 40, out_path: Path | None = None) -> dict:
    """Full frontier AU residual feasibility audit (cutoff vs lost continuation)."""
    art = audit_frontier_unfulfilled(iterations=iterations, limit=None)
    # audit already includes residual fields when AU present
    label_counts = Counter(r["label"] for r in art["rows"])
    cutoff_feasible = sum(
        1 for r in art["rows"] if r.get("cutoff_vs_infeasibility") == "cutoff_with_feasible_continuation"
    )
    cutoff_infeas = sum(
        1 for r in art["rows"] if r.get("cutoff_vs_infeasibility") == "cutoff_with_infeasible_or_unknown_continuation"
    )
    residual_ok = sum(1 for r in art["rows"] if r.get("residual_feasible") is True)
    residual_bad = sum(1 for r in art["rows"] if r.get("residual_feasible") is False)
    residual_skip = sum(1 for r in art["rows"] if r.get("residual_check") == "skipped" or "residual_check" not in r)
    summary = {
        "n_audited": art["n_audited"],
        "n_source_au_rows": art["n_source_au_rows"],
        "label_counts": dict(label_counts),
        "cutoff_with_feasible_continuation": cutoff_feasible,
        "cutoff_with_infeasible_or_unknown_continuation": cutoff_infeas,
        "residual_feasible_true": residual_ok,
        "residual_feasible_false": residual_bad,
        "residual_skipped": residual_skip,
        "note": (
            "Cutoff alone does not prove loss of a feasible continuation. "
            "residual_feasible tests nominal commitment continuation at the final observation."
        ),
        "rows": art["rows"],
    }
    path = out_path or Path("docs/mpc_central/phase3d_au_residual.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def scientific_verdict(fork_values: dict, decision: dict, closed: dict, au_audit: dict | None = None) -> dict:
    fairness = decision["fairness"]
    fragile = list(fairness.get("fragile_notes") or [])
    predictive_wins = 0
    predictive_losses = 0
    notes = []
    for row in closed["rows"]:
        b1 = row["controllers"]["b1"]
        pred = row["controllers"]["predictive_uniform"]
        if not pred["replay_ok"] or not b1["replay_ok"]:
            notes.append(f"{row['case_id']}: replay failure")
            continue
        better_completed = pred["completed_count"] > b1["completed_count"]
        better_au = pred["accepted_unfulfilled_count"] < b1["accepted_unfulfilled_count"]
        worse_completed = pred["completed_count"] < b1["completed_count"]
        worse_au = pred["accepted_unfulfilled_count"] > b1["accepted_unfulfilled_count"]
        if (better_completed or better_au) and not (worse_completed or worse_au):
            predictive_wins += 1
            notes.append(f"{row['case_id']}: predictive improves vs B1")
        elif worse_completed or worse_au:
            predictive_losses += 1
            notes.append(f"{row['case_id']}: predictive worse vs B1")
        else:
            notes.append(f"{row['case_id']}: predictive indistinguishable from B1 on completed/AU")

    ada_vs_eq = []
    for h in decision["head_to_head_base"]:
        if h["adaptive_regret"] + 1e-9 < h["equal_regret"]:
            ada_vs_eq.append("adaptive")
        elif h["equal_regret"] + 1e-9 < h["adaptive_regret"]:
            ada_vs_eq.append("equal")
        else:
            ada_vs_eq.append("tie")

    if predictive_wins > 0 and predictive_losses == 0 and not fragile:
        verdict = "GO"
        reason = (
            "Predictive MPC shows a defensible closed-loop gain vs B1 without fragile adaptive allocation dependence."
        )
    elif predictive_wins > 0 and (predictive_losses > 0 or fragile):
        verdict = "REVISE"
        reason = (
            "Some predictive closed-loop gains exist, but results remain fragile or mixed against strong baselines."
        )
    else:
        verdict = "REVISE"
        reason = (
            "Evidence does not yet support claiming a novel MPC contribution over established rollout/B1 baselines."
        )

    supported = [
        "Executed distance now uses arc-table reconstruction (nonzero on traveled routes).",
        "Scenario recourse default is B1-validated; insertion retained as labeled baseline.",
        "sampled_expectation no longer renormalizes over partial samples.",
        "CommitmentSafePredictiveMpc uses causal closed-loop scenario rollouts on the real plant.",
        "Forecast fitted on train split only; development pilot; holdout untouched.",
    ]
    unproved = [
        "Order-robust adaptive allocation advantage (Phase 3C fragile wins remain).",
        "Global multistage optimality of the offline first-action reference.",
        "Superiority of the predictive controller over B1 / equal / CRN as a paper claim.",
        "Holdout generalization (intentionally unevaluated).",
    ]
    if au_audit is not None:
        supported.append(
            f"AU residual audit: {au_audit['n_audited']} episodes; "
            f"cutoff_feasible={au_audit['cutoff_with_feasible_continuation']}, "
            f"cutoff_infeas_or_unknown={au_audit['cutoff_with_infeasible_or_unknown_continuation']}."
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "predictive_wins_vs_b1": predictive_wins,
        "predictive_losses_vs_b1": predictive_losses,
        "adaptive_vs_equal_base": dict(
            adaptive=ada_vs_eq.count("adaptive"),
            equal=ada_vs_eq.count("equal"),
            tie=ada_vs_eq.count("tie"),
        ),
        "fairness_verdict": fairness["verdict"],
        "fragile_notes": fragile,
        "notes": notes,
        "supported": supported,
        "unproved": unproved,
    }


def run_phase3d_pilot(*, out_path: Path | None = None, run_au_audit: bool = True) -> dict:
    fork_values = repaired_fork_action_values()
    decision = decision_layer_pilot()
    closed = closed_loop_pilot()
    au_audit = None
    au_summary = None
    if run_au_audit:
        au_path = Path("docs/mpc_central/phase3d_au_residual.json")
        au_audit = run_au_residual_audit(iterations=40, out_path=au_path)
        au_summary = {
            "n_audited": au_audit["n_audited"],
            "label_counts": au_audit["label_counts"],
            "cutoff_with_feasible_continuation": au_audit["cutoff_with_feasible_continuation"],
            "cutoff_with_infeasible_or_unknown_continuation": au_audit[
                "cutoff_with_infeasible_or_unknown_continuation"
            ],
            "residual_feasible_true": au_audit["residual_feasible_true"],
            "residual_feasible_false": au_audit["residual_feasible_false"],
            "artifact": str(au_path),
        }
    verdict = scientific_verdict(fork_values, decision, closed, au_summary)
    fairness = decision["fairness"]
    artifact = {
        "phase": "3D",
        "verdict": verdict["verdict"],
        "reason": verdict["reason"],
        "scientific": verdict,
        "splits": closed["split"],
        "repaired_fork_values": fork_values,
        "fairness_summary": {
            "n_comparisons": fairness["n_comparisons"],
            "adaptive_better": fairness["adaptive_better"],
            "adaptive_worse": fairness["adaptive_worse"],
            "ties": fairness["ties"],
            "fragile_notes": fairness["fragile_notes"],
            "verdict": fairness["verdict"],
            "estimation_note": fairness.get("estimation_note"),
            "reference_label": fairness.get("reference_label"),
        },
        "head_to_head_base": decision["head_to_head_base"],
        "closed_loop": closed,
        "au_residual_summary": au_summary,
        "mean_closed_loop_optimize_seconds": {
            name: mean(r["controllers"][name]["optimize_seconds"] for r in closed["rows"])
            for name in closed["rows"][0]["controllers"]
        }
        if closed["rows"]
        else {},
    }
    path = out_path or Path("docs/mpc_central/phase3d_results.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    art = run_phase3d_pilot()
    print(art["verdict"], art["reason"])
