"""Phase 3D development pilot: repaired plant + closed-loop predictive MPC.

Modest matched comparisons only. Holdout untouched. No large benchmarks.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, TrainDemandAtom, build_anonymous_scenarios
from safe_time_evrp.mpc3c.seeds import stable_seed
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
from safe_time_evrp.validation.replay import validate_log


def _train_forecast_from_instance(instance, *, n_scenarios: int = 2, seed: int = 0) -> ArrivalForecast:
    """Fit anonymous atoms from *this* instance geometry only (development, not holdout)."""
    atoms: list[TrainDemandAtom] = []
    for cid in instance.customer_ids():
        node = instance.node(cid)
        atoms.append(
            TrainDemandAtom(
                float(node.x),
                float(node.y),
                float(node.demand),
                float(node.service_time),
                float(node.window.ready),
                float(node.window.due),
            )
        )
    model = ArrivalForecast(train_atoms=tuple(atoms), train_interarrival_mean=5.0, model_id="phase3d_dev")
    return build_anonymous_scenarios(
        model,
        n_scenarios=n_scenarios,
        customers_per_scenario=min(3, max(1, len(atoms) // 2)),
        seed=stable_seed("phase3d", str(seed)),
    )


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
    # Matched adaptive vs equal / CRN on base tags only.
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
                "notes": list(d.notes)[:4],
            }
        )
    overrun = sum(1 for d in result.decisions if (d.audit or {}).get("predictive_mpc", {}).get("deadline_overrun"))
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
        "first_decisions": first_actions,
        "completed": completed,
        "accepted_unfulfilled": au,
    }


def closed_loop_pilot(*, alns_iterations: int = 15, alns_time: float = 0.15, seed: int = 7) -> dict:
    """Small matched closed-loop on the first two baseline development cases."""
    cases = build_baseline_suite()[:2]
    rows = []
    for case in cases:
        forecast = _train_forecast_from_instance(case.instance, n_scenarios=2, seed=seed)
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
            ),
        }
        case_row = {"case_id": case.case_id, "fleet_size": case.fleet_size, "controllers": {}}
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
    return {"n_cases": len(rows), "rows": rows}


def scientific_verdict(fork_values: dict, decision: dict, closed: dict) -> dict:
    fairness = decision["fairness"]
    fragile = list(fairness.get("fragile_notes") or [])
    # Closed-loop: does predictive beat B1 on completed or AU at matched budget?
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
        if better_completed or better_au:
            if worse_completed or worse_au:
                notes.append(f"{row['case_id']}: mixed predictive vs B1")
            else:
                predictive_wins += 1
                notes.append(f"{row['case_id']}: predictive improves vs B1")
        elif worse_completed or worse_au:
            predictive_losses += 1
            notes.append(f"{row['case_id']}: predictive worse vs B1")
        else:
            notes.append(f"{row['case_id']}: predictive indistinguishable from B1 on completed/AU")

    # Adaptive vs equal on base head-to-head
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
    elif all(x == "tie" for x in ada_vs_eq) and predictive_wins == 0:
        verdict = "REVISE"
        reason = (
            "Repaired evaluation contracts are in place, but the predictive controller does not yet "
            "show a mechanism-specific closed-loop advantage over B1 / equal allocation."
        )
    else:
        verdict = "REVISE"
        reason = (
            "Evidence does not yet support claiming a novel MPC contribution over established rollout/B1 baselines."
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
        "supported": [
            "Executed distance now uses arc-table reconstruction (nonzero on traveled routes).",
            "Scenario recourse default is B1-validated; insertion retained as labeled baseline.",
            "sampled_expectation no longer renormalizes over partial samples.",
            "CommitmentSafePredictiveMpc runs on the real plant via run_episode.",
        ],
        "unproved": [
            "Order-robust adaptive allocation advantage (Phase 3C fragile wins remain).",
            "Global multistage optimality of the offline first-action reference.",
            "Train/holdout forecast generalization (pilot uses development atoms only).",
            "Superiority of the predictive controller over B1 / equal / CRN as a paper claim.",
        ],
    }


def run_phase3d_pilot(*, out_path: Path | None = None) -> dict:
    fork_values = repaired_fork_action_values()
    decision = decision_layer_pilot()
    closed = closed_loop_pilot()
    verdict = scientific_verdict(fork_values, decision, closed)
    # Compact fairness for artifact (full comparisons retained).
    fairness = decision["fairness"]
    artifact = {
        "phase": "3D",
        "verdict": verdict["verdict"],
        "reason": verdict["reason"],
        "scientific": verdict,
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
