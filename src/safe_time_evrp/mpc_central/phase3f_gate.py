"""Phase 3F mechanism feasibility gate runner."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Observation, VehicleStatus
from safe_time_evrp.mpc3c.forecast import visible_forecast
from safe_time_evrp.mpc_central.accelerated_pilot import build_accelerated_dev_matrix
from safe_time_evrp.mpc_central.commitment_viability import (
    analyze_viability_vs_rollout_ranking,
    profile_decision_viability,
)
from safe_time_evrp.mpc_central.counterfactual_actions import (
    FirstActionKey,
    eligible_new_accepts,
    generate_counterfactual_actions,
)
from safe_time_evrp.mpc_central.decision_oracle import run_restricted_decision_oracle
from safe_time_evrp.mpc_central.paired_b1_eval import paired_evaluate_epoch
from safe_time_evrp.mpc_central.phase3d_splits import fit_train_forecast
from safe_time_evrp.mpc_central.switching_mpc import (
    IMPROVEMENT_THRESHOLD,
    REQUIRE_HOEFFDING_LCB,
    RISK_FLOOR,
    CommitmentViabilitySwitchingMpc,
)
from safe_time_evrp.validation.replay import validate_log

FOCUS_CASES = ("A_dense_arrivals", "A_low_soc_charge", "B_easy_dynamic")
SEEDS = (3, 7, 11)


def _case_map():
    return {c.case_id: c for c in build_accelerated_dev_matrix()}


def reproduce_in_service_admission_bug(case_id: str = "A_low_soc_charge", *, seed: int = 7) -> dict:
    """Drive plant until an in-service customer appears; check counterfactual eligibility."""
    case = _case_map()[case_id]
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    # Advance with B1 until someone is in service and another vehicle is idle.
    b1 = FullValidationAlnsMpc(case.instance, case.horizon, iterations=8, time_limit_seconds=0.15, seed=seed)
    events = 0
    target_obs: Observation | None = None
    while events < 500:
        nxt = sim.next_event_time()
        if nxt is None:
            break
        ev = sim.pop_event()
        events += 1
        if ev is None:
            break
        if ev.kind in {"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan"}:
            obs = sim.observation()
            if obs.in_service and any(
                (v.status == VehicleStatus.IDLE or v.status == "idle") and v.locked_destination is None
                for v in obs.vehicles
            ):
                target_obs = obs
                break
            d = b1.decide(obs, ev.kind)
            sim.apply_decision(d)
    if target_obs is None:
        return {"reproduced_state": False, "notes": ["no_in_service_idle_state_found"]}

    illegal = [c for c in eligible_new_accepts(target_obs) if c in target_obs.in_service]
    cands, diag = generate_counterfactual_actions(
        case.instance,
        target_obs,
        horizon=case.horizon,
        alns_iterations=6,
        alns_time=0.1,
        seed=seed,
    )
    bad_newly = []
    bad_legs = []
    for name, d in cands:
        for c in d.newly_accepted:
            if c in target_obs.in_service:
                bad_newly.append({"name": name, "customer": c})
        key = FirstActionKey.from_decision(d)
        for vid, node, purpose in key.first_legs:
            if purpose == "service" and node in target_obs.in_service:
                bad_legs.append({"name": name, "leg": [vid, node, purpose]})
    return {
        "reproduced_state": True,
        "time": target_obs.time,
        "in_service": list(target_obs.in_service),
        "released_open": list(target_obs.released_open),
        "accepted": list(target_obs.accepted),
        "eligible_new_accepts": eligible_new_accepts(target_obs),
        "illegal_eligible": illegal,
        "n_candidates": len(cands),
        "bad_newly_accepted": bad_newly,
        "bad_service_legs_to_in_service": bad_legs,
        "pass": not illegal and not bad_newly and not bad_legs,
        "diag_notes": list(diag.notes),
    }


def viability_probe(case_id: str = "A_low_soc_charge", *, seed: int = 7) -> dict:
    case = _case_map()[case_id]
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    # First decision epoch
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    if not obs.released_open:
        ev = sim.pop_event()
        if ev and ev.kind == "request_release":
            obs = sim.observation()
    scenarios = [visible_forecast(obs, forecast, case.horizon, scenario_index=i) for i in range(2)]
    b1, reports = paired_evaluate_epoch(
        case.instance,
        obs,
        horizon=case.horizon,
        scenario_forecasts=scenarios,
        alns_iterations=8,
        alns_time=0.2,
        seed=seed,
        max_replan_interval=case.max_replan_interval,
        max_events=120,
    )
    ranked = []
    for r in reports:
        if r.mean_delta is None and r.name != "b1":
            continue
        # Use candidate causal mean approximated as b1_value + mean_delta when available.
        if r.name == "b1":
            val = 0.0
            if r.pairs:
                val = sum(p.b1_value for p in r.pairs if p.valid_for_comparison) / max(
                    1, sum(1 for p in r.pairs if p.valid_for_comparison)
                )
        else:
            val = r.mean_delta or -1e9
        ranked.append((r.name, r.candidate, val))
    ranked.sort(key=lambda x: x[2], reverse=True)
    analysis = analyze_viability_vs_rollout_ranking(case.instance, obs, ranked[:6], horizon=case.horizon)
    b1_prof = profile_decision_viability(case.instance, obs, b1, horizon=case.horizon)
    analysis["b1_profile"] = {
        "commitment_ok": b1_prof.commitment_ok,
        "min_window_slack": b1_prof.min_window_slack,
        "min_end_soc": b1_prof.min_end_soc,
        "total_charge_time": b1_prof.total_charge_time,
        "min_load_residual": b1_prof.min_load_residual,
    }
    analysis["case_id"] = case_id
    analysis["seed"] = seed
    analysis["time"] = obs.time
    return analysis


def matched_phase3f_eval(
    *,
    case_ids: tuple[str, ...] = FOCUS_CASES,
    seeds: tuple[int, ...] = SEEDS,
    alns_iterations: int = 10,
    alns_time: float = 0.35,
) -> dict:
    cases = _case_map()
    forecast_by_seed = {
        s: fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=s, announcement_mean=12.0) for s in seeds
    }
    rows = []
    for case_id in case_ids:
        case = cases[case_id]
        for seed in seeds:
            forecast = forecast_by_seed[seed]
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
                "switching_mpc": CommitmentViabilitySwitchingMpc(
                    case.instance,
                    case.horizon,
                    forecast=forecast,
                    n_scenarios=2,
                    alns_iterations=alns_iterations,
                    time_limit_seconds=alns_time,
                    seed=seed,
                    use_forecast=True,
                    allow_switching=True,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=200,
                ),
                "no_forecast_switching": CommitmentViabilitySwitchingMpc(
                    case.instance,
                    case.horizon,
                    forecast=forecast,
                    n_scenarios=2,
                    alns_iterations=alns_iterations,
                    time_limit_seconds=alns_time,
                    seed=seed,
                    use_forecast=False,
                    allow_switching=True,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=200,
                ),
                "no_switching_ablation": CommitmentViabilitySwitchingMpc(
                    case.instance,
                    case.horizon,
                    forecast=forecast,
                    n_scenarios=2,
                    alns_iterations=alns_iterations,
                    time_limit_seconds=alns_time,
                    seed=seed,
                    use_forecast=True,
                    allow_switching=False,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=200,
                ),
            }
            cell = {"case_id": case_id, "seed": seed, "controllers": {}}
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
                rep = validate_log(case.instance, res.log)
                final = res.final_requests
                switches = getattr(getattr(ctrl, "profile", None), "switches", None)
                cell["controllers"][name] = {
                    "completed_count": sum(1 for st in final.values() if st == "completed"),
                    "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
                    "rejected_count": sum(1 for st in final.values() if st == "rejected"),
                    "executed_distance": executed_distance_from_log(case.instance, res.log),
                    "optimize_seconds": res.optimize_seconds,
                    "replay_ok": rep.ok,
                    "replay_code": rep.code,
                    "n_switches": switches,
                }
            b1 = cell["controllers"]["b1"]
            sw = cell["controllers"]["switching_mpc"]
            stoch = cell["controllers"]["stochastic_uniform"]
            cell["paired"] = {
                "switching_minus_b1_completed": sw["completed_count"] - b1["completed_count"],
                "switching_minus_b1_au": sw["accepted_unfulfilled_count"] - b1["accepted_unfulfilled_count"],
                "switching_minus_stoch_completed": sw["completed_count"] - stoch["completed_count"],
                "switching_equals_b1": (
                    sw["completed_count"] == b1["completed_count"]
                    and sw["accepted_unfulfilled_count"] == b1["accepted_unfulfilled_count"]
                    and abs(sw["executed_distance"] - b1["executed_distance"]) < 1e-9
                ),
                "switching_equals_stoch": (
                    sw["completed_count"] == stoch["completed_count"]
                    and sw["accepted_unfulfilled_count"] == stoch["accepted_unfulfilled_count"]
                    and abs(sw["executed_distance"] - stoch["executed_distance"]) < 1e-9
                ),
                "valid_for_claim": sw["replay_ok"] and b1["replay_ok"],
            }
            rows.append(cell)
    valid = [r for r in rows if r["paired"]["valid_for_claim"]]
    wins = sum(
        1
        for r in valid
        if r["paired"]["switching_minus_b1_completed"] > 0 and r["paired"]["switching_minus_b1_au"] <= 0
    )
    losses = sum(
        1 for r in valid if r["paired"]["switching_minus_b1_completed"] < 0 or r["paired"]["switching_minus_b1_au"] > 0
    )
    equals_b1 = sum(1 for r in valid if r["paired"]["switching_equals_b1"])
    equals_stoch = sum(1 for r in valid if r["paired"]["switching_equals_stoch"])
    total_switches = sum(r["controllers"]["switching_mpc"]["n_switches"] or 0 for r in rows)
    return {
        "seeds": list(seeds),
        "case_ids": list(case_ids),
        "n_cells": len(rows),
        "n_valid_cells": len(valid),
        "wins_vs_b1_valid": wins,
        "losses_vs_b1_valid": losses,
        "equals_b1_valid": equals_b1,
        "equals_stoch_valid": equals_stoch,
        "total_switches": total_switches,
        "hyperparameters": {
            "improvement_threshold": IMPROVEMENT_THRESHOLD,
            "risk_floor": RISK_FLOOR,
            "require_hoeffding_lcb": REQUIRE_HOEFFDING_LCB,
            "tuned_on_phase3e_seeds": False,
        },
        "rows": rows,
    }


def decide_gate(admission: dict, viability: dict, oracle: dict, matched: dict) -> dict:
    distinct = matched["equals_stoch_valid"] < matched["n_valid_cells"]
    makes_switches = matched["total_switches"] > 0
    better = matched["wins_vs_b1_valid"] > matched["losses_vs_b1_valid"]
    admission_ok = admission.get("pass", False)
    viability_signal = viability.get("contribution") != "NO_ADDITIONAL_SIGNAL"
    oracle_nonmyopic = bool(oracle.get("captures_nonmyopic_charge"))

    if not admission_ok:
        decision = "NO-GO"
        reason = "Admission/in-service semantics still allow invalid first actions."
    elif not distinct and not makes_switches:
        decision = "NO-GO"
        reason = (
            "Switching controller did not produce decisions distinct from B1/stochastic "
            "rollout under matched development cells."
        )
    elif makes_switches and better and (viability_signal or oracle_nonmyopic):
        decision = "GO_PROTOTYPE"
        reason = (
            "Baseline-anchored switching is algorithmically distinct, plant-valid, made "
            "nonmyopic switches, and showed credible development wins worth expanding."
        )
    elif makes_switches or distinct:
        decision = "REVISE"
        reason = (
            "Mechanism is valid and distinct from unguarded rollout, but mostly defaults to B1, "
            "lacks a strong EVRP-specific viability differentiator, or shows mixed performance."
        )
    else:
        decision = "REVISE"
        reason = "Valid scaffolding without clear mechanism-specific advantage on the gate."

    return {
        "decision": decision,
        "reason": reason,
        "checks": {
            "admission_ok": admission_ok,
            "algorithmically_distinct": distinct or makes_switches,
            "made_switches": makes_switches,
            "better_than_b1": better,
            "viability_signal": viability_signal,
            "oracle_nonmyopic": oracle_nonmyopic,
        },
    }


def run_phase3f(*, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or Path("docs/mpc_central")
    out_dir.mkdir(parents=True, exist_ok=True)

    admission = reproduce_in_service_admission_bug()
    viability = viability_probe()
    oracle = run_restricted_decision_oracle()
    matched = matched_phase3f_eval()
    gate = decide_gate(admission, viability, oracle, matched)

    artifact = {
        "phase": "3F",
        "reviewed_parent_sha": "3da83327c8d35cd7839b29dde76e72c2f2a10173",
        "admission_repair": admission,
        "viability_analysis": viability,
        "decision_oracle": oracle,
        "matched_evaluation": matched,
        "gate": gate,
    }
    (out_dir / "phase3f_results.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    art = run_phase3f()
    print(art["gate"]["decision"], art["gate"]["reason"])
    m = art["matched_evaluation"]
    print(
        "matched",
        m["wins_vs_b1_valid"],
        m["losses_vs_b1_valid"],
        m["equals_b1_valid"],
        m["total_switches"],
    )
