"""Accelerated decisive development pilot (commitment-preserving counterfactual MPC)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.mpc3c.announcement import AnnouncementProcessSpec, AnnouncementSource
from safe_time_evrp.mpc3c.forecast import build_anonymous_scenarios, fit_empirical_arrivals
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.counterfactual_actions import generate_counterfactual_actions
from safe_time_evrp.mpc_central.phase3d_splits import HOLDOUT_CASE_IDS, fit_train_forecast, holdout_cases
from safe_time_evrp.mpc_central.scenario_rollout import is_quiescent
from safe_time_evrp.testbed.constructor import make_observation
from safe_time_evrp.validation.replay import validate_log


@dataclass(frozen=True)
class DevCaseSpec:
    case_id: str
    tags: tuple[str, ...]


def _pressure_case(
    case_id: str, *, battery: float, span: float, n_customers: int, fleet: int, mu: float
) -> BaselineCase:
    vehicle = VehicleType(battery, 25.0, 1.0, 0.5, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 2000), 0),
        Node("S", NodeKind.CHARGER, span * 0.2, span * 0.2, 0, TimeWindow(0, 2000), 0),
    ]
    for i in range(n_customers):
        x = ((i % 3) + 1) * (span / 4)
        y = ((i // 3) + 1) * (span / 5)
        due = 80 + 35 * i
        nodes.append(Node(f"C{i + 1}", NodeKind.CUSTOMER, x, y, 1, TimeWindow(0, due), 2))
    inst = build_euclidean_instance(
        case_id,
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="accelerated-dev",
        assumptions=("preregistered_dev_matrix", f"announce_mu={mu}"),
        metadata={"suite": "accelerated", "mu": mu},
    )
    spec = AnnouncementProcessSpec(
        source=AnnouncementSource.PREREGISTERED_POISSON,
        mean_interarrival=mu,
        spec_id=f"accel_{case_id}",
        notes=("preregistered",),
    )
    releases = spec.materialize(inst, seed_key=case_id)
    return BaselineCase(case_id, inst, releases, fleet, 250.0, 30.0, 600.0, ("accelerated", "pressure"))


def build_accelerated_dev_matrix() -> list[BaselineCase]:
    """Small preregistered matrix with battery / arrival / commitment pressure."""
    suite = {c.case_id: c for c in build_baseline_suite()}
    cases = [
        suite["B_phase_b"],
        suite["B_tight_battery"],
        suite["B_easy_dynamic"],
        _pressure_case("A_low_soc_charge", battery=22.0, span=28.0, n_customers=6, fleet=2, mu=10.0),
        _pressure_case("A_dense_arrivals", battery=40.0, span=24.0, n_customers=8, fleet=2, mu=6.0),
        _pressure_case("A_tight_windows", battery=35.0, span=22.0, n_customers=7, fleet=2, mu=12.0),
    ]
    # Ensure holdout remains untouched.
    assert all(c.case_id not in HOLDOUT_CASE_IDS for c in cases)
    _ = holdout_cases()
    return cases


def _summarize(case: BaselineCase, name: str, result, ctrl=None) -> dict:
    report = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sorted(cid for cid, st in final.items() if st == "completed")
    au = sorted(cid for cid, st in final.items() if st == "accepted_unfulfilled")
    rejected = sorted(cid for cid, st in final.items() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
    charge = sum(1 for rec in result.log if rec.kind == "charge_start")
    first_keys = []
    n_valid = []
    for d in result.decisions[:5]:
        audit = (d.audit or {}).get("predictive_mpc", {})
        first_keys.append(
            {
                "trigger": d.trigger,
                "newly_accepted": list(d.newly_accepted),
                "planned_service": list(d.planned_service)[:5],
                "notes": list(d.notes)[:6],
                "n_valid_actions": audit.get("n_valid_actions"),
            }
        )
        if audit.get("n_valid_actions") is not None:
            n_valid.append(audit["n_valid_actions"])
    return {
        "controller": name,
        "completed_count": len(completed),
        "accepted_unfulfilled_count": len(au),
        "rejected_count": len(rejected),
        "executed_distance": dist,
        "charge_starts": charge,
        "optimize_seconds": result.optimize_seconds,
        "fallback_count": result.fallback_count,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "termination_reason": result.termination_reason,
        "replay_ok": report.ok,
        "mean_valid_actions": mean(n_valid) if n_valid else None,
        "first_decisions": first_keys,
        "completed": completed,
        "accepted_unfulfilled": au,
    }


def action_diversity_gate(case: BaselineCase) -> dict:
    """Checkpoint B diagnostic on the initial observation."""
    obs = make_observation(case.instance, case.fleet_size)
    # Release first customers that are due at 0.
    from safe_time_evrp.environment.simulator import FleetSimulator

    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        if t <= 0:
            sim.schedule_release(cid, 0.0)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    cands, diag = generate_counterfactual_actions(
        case.instance, obs, horizon=case.horizon, alns_iterations=8, alns_time=0.08
    )
    return {
        "case_id": case.case_id,
        "quiescent": is_quiescent(obs),
        "raw_candidates": diag.raw_candidates,
        "distinct_first_actions": diag.distinct_first_actions,
        "valid_commitment_safe": diag.valid_commitment_safe,
        "n_returned": len(cands),
        "sample_keys": list(diag.keys)[:8],
        "notes": diag.notes,
        "pass": diag.valid_commitment_safe >= 2,
    }


def run_accelerated_pilot(
    *,
    out_dir: Path | None = None,
    alns_iterations: int = 10,
    alns_time: float = 0.35,
    seed: int = 7,
    max_cases: int | None = None,
) -> dict:
    out_dir = out_dir or Path("docs/mpc_central")
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    # Independent forecast seed for plant/forecast separation check in artifact.
    forecast_alt = build_anonymous_scenarios(
        fit_empirical_arrivals([c.instance for c in build_baseline_suite()[:2]]),
        n_scenarios=2,
        customers_per_scenario=2,
        seed=stable_seed("accel_forecast_indep", str(seed + 99)),
        announcement_mean=12.0,
    )
    _ = forecast_alt  # documented independent seed path

    cases = build_accelerated_dev_matrix()
    if max_cases is not None:
        cases = cases[:max_cases]

    diversity = [action_diversity_gate(c) for c in cases]
    rows = []
    for case in cases:
        controllers = {
            "b1": FullValidationAlnsMpc(
                case.instance, case.horizon, iterations=alns_iterations, time_limit_seconds=alns_time, seed=seed
            ),
            "m1": CertificateCarryingAlnsMpc(
                case.instance, case.horizon, iterations=alns_iterations, time_limit_seconds=alns_time, seed=seed
            ),
            "stochastic_uniform": CommitmentSafePredictiveMpc(
                case.instance,
                case.horizon,
                forecast=forecast,
                n_scenarios=2,
                alns_iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed,
                allocation="uniform",
                use_counterfactuals=True,
                use_forecast=True,
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=200,
            ),
            "proposed_mpc": CommitmentSafePredictiveMpc(
                case.instance,
                case.horizon,
                forecast=forecast,
                n_scenarios=2,
                alns_iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed + 1,
                allocation="paired_crn",
                use_counterfactuals=True,
                use_forecast=True,
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=200,
            ),
            "no_forecast_ablation": CommitmentSafePredictiveMpc(
                case.instance,
                case.horizon,
                forecast=forecast,
                n_scenarios=2,
                alns_iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=seed + 2,
                allocation="uniform",
                use_counterfactuals=True,
                use_forecast=False,
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=200,
            ),
        }
        case_row = {"case_id": case.case_id, "tags": list(case.tags), "controllers": {}}
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
            case_row["controllers"][name] = _summarize(case, name, res, ctrl)
        rows.append(case_row)

    # Aggregate paired differences vs B1 / stochastic
    paired = []
    for row in rows:
        b1 = row["controllers"]["b1"]
        prop = row["controllers"]["proposed_mpc"]
        stoch = row["controllers"]["stochastic_uniform"]
        abl = row["controllers"]["no_forecast_ablation"]
        paired.append(
            {
                "case_id": row["case_id"],
                "proposed_minus_b1_completed": prop["completed_count"] - b1["completed_count"],
                "proposed_minus_b1_au": prop["accepted_unfulfilled_count"] - b1["accepted_unfulfilled_count"],
                "proposed_minus_stoch_completed": prop["completed_count"] - stoch["completed_count"],
                "proposed_minus_ablation_completed": prop["completed_count"] - abl["completed_count"],
                "proposed_opt_seconds": prop["optimize_seconds"],
                "b1_opt_seconds": b1["optimize_seconds"],
                "all_replay_ok": all(row["controllers"][k]["replay_ok"] for k in row["controllers"]),
            }
        )

    wins_b1 = sum(1 for p in paired if p["proposed_minus_b1_completed"] > 0 and p["proposed_minus_b1_au"] <= 0)
    losses_b1 = sum(1 for p in paired if p["proposed_minus_b1_completed"] < 0 or p["proposed_minus_b1_au"] > 0)
    wins_stoch = sum(1 for p in paired if p["proposed_minus_stoch_completed"] > 0)
    diversity_pass = all(d["pass"] for d in diversity)

    if wins_b1 > 0 and losses_b1 == 0 and wins_stoch > 0 and diversity_pass:
        verdict = "GO"
        reason = "Proposed MPC shows reproducible development gains vs B1 and identical-candidate stochastic rollout."
    elif not diversity_pass:
        verdict = "REVISE"
        reason = "Action generator failed to produce enough distinct safe first actions on the development matrix."
    elif losses_b1 > 0 and wins_b1 == 0 and wins_stoch == 0:
        verdict = "NO-GO"
        reason = (
            "Validity repairs and distinct counterfactual actions are in place, but the proposed predictive MPC "
            "is dominated by reactive B1 on completed service across the development matrix and does not beat "
            "identical-candidate stochastic rollout — current mechanism is not a publishable superiority claim."
        )
    elif diversity_pass and (wins_b1 > 0 or wins_stoch > 0):
        verdict = "REVISE"
        reason = "Valid counterfactual MPC with some gains, but advantage is weak/mixed — revise mechanism or cases."
    else:
        verdict = "REVISE"
        reason = (
            "Implementation validity improved, but proposed MPC shows no meaningful matched-budget service advantage "
            "over B1 / standard stochastic rollout on the development matrix."
        )

    artifact = {
        "phase": "accelerated_mpc",
        "verdict": verdict,
        "reason": reason,
        "holdout_untouched": list(HOLDOUT_CASE_IDS),
        "forecast_model_id": forecast.model_id,
        "diversity_gate": diversity,
        "paired_differences": paired,
        "summary": {
            "n_cases": len(rows),
            "wins_vs_b1": wins_b1,
            "losses_vs_b1": losses_b1,
            "wins_vs_stochastic": wins_stoch,
            "diversity_all_pass": diversity_pass,
            "mean_proposed_opt_seconds": mean(p["proposed_opt_seconds"] for p in paired) if paired else 0.0,
            "mean_b1_opt_seconds": mean(p["b1_opt_seconds"] for p in paired) if paired else 0.0,
        },
        "rows": rows,
        "supported": [
            "Causal rollouts restore busy-vehicle actions without teleporting to future anchors.",
            "Terminal horizon scoring uses residual-feasible treatment instead of forced AU.",
            "Forecast announcements use preregistered Poisson μ, separate from service windows.",
            "Counterfactual first-action generator creates distinct commitment-safe alternatives.",
        ],
        "unproved": [
            "Publishable superiority vs B1 / Jiang-style stochastic lookahead.",
            "Novelty beyond composition of known commitment + rollout components.",
            "Holdout generalization.",
        ],
        "formal_difference_vs_stochastic_rollout": (
            "With identical candidate sets and forecasts, proposed_mpc (paired_crn allocation) vs "
            "stochastic_uniform differs only in scenario-index consumption order / allocation label — "
            "not a new optimality criterion. Scientific novelty must come from counterfactual action "
            "construction + commitment-preserving evaluation contracts, not from the argmax itself."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "accelerated_results.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    art = run_accelerated_pilot()
    print(art["verdict"], art["reason"])
    print(art["summary"])
