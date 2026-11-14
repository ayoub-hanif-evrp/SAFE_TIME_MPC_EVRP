"""Phase 3E: decision-level causal audit of repaired predictive MPC."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc_central.accelerated_pilot import build_accelerated_dev_matrix
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey, generate_counterfactual_actions
from safe_time_evrp.mpc_central.phase3d_splits import fit_train_forecast
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, rollout_candidate
from safe_time_evrp.mpc3c.forecast import visible_forecast
from safe_time_evrp.validation.replay import validate_log

FOCUS_CASES = ("A_dense_arrivals", "A_low_soc_charge", "B_easy_dynamic")


class _CapturePair:
    """Run B1 and predictive MPC on the same plant by dual controllers is impossible;
    instead we capture decisions from one controller while recording observations.
    """

    def __init__(self, inner, name: str):
        self.inner = inner
        self.name = name
        self.epochs: list[dict] = []

    def decide(self, observation: Observation, trigger: str) -> Decision:
        d = self.inner.decide(observation, trigger)
        key = FirstActionKey.from_decision(d)
        audit = (d.audit or {}).get("predictive_mpc", {})
        self.epochs.append(
            {
                "trigger": trigger,
                "time": observation.time,
                "released_open": list(observation.released_open),
                "accepted": list(observation.accepted),
                "completed": list(observation.completed),
                "vehicles": [
                    {
                        "id": v.id,
                        "status": v.status,
                        "node": v.node,
                        "soc": v.soc,
                        "load": v.load,
                        "locked": v.locked_destination,
                    }
                    for v in observation.vehicles
                ],
                "newly_accepted": list(d.newly_accepted),
                "rejected": list(d.rejected),
                "first_legs": [list(x) for x in key.first_legs],
                "notes": list(d.notes)[:8],
                "n_valid_actions": audit.get("n_valid_actions"),
                "optimize_seconds": d.optimize_seconds,
            }
        )
        return d


def _case_map():
    return {c.case_id: c for c in build_accelerated_dev_matrix()}


def fairness_contract_report(*, seed: int = 7) -> dict:
    """Document that allocation labels do not change selection; seeds must match."""
    return {
        "finding": "EQUIVALENT_TO_STOCHASTIC_ROLLOUT",
        "details": (
            "CommitmentSafePredictiveMpc.allocation is recorded in notes/audit but does not alter "
            "candidate generation, scenario construction, or argmax. Differing ALNS seeds "
            "(seed vs seed+1) change candidates and can fabricate a false proposed-vs-stochastic win."
        ),
        "required_contract": {
            "same_observation": True,
            "same_candidate_set_and_order": True,
            "same_forecast_scenarios": True,
            "same_recourse": "b1_validated",
            "same_score_definition": True,
            "same_seed": True,
            "same_time_limit": True,
        },
        "pilot_seed_used_for_fair_rerun": seed,
        "algorithmic_difference_if_seeds_matched": "none — identical argmax over identical rollouts",
    }


def diagnose_replay(case_id: str, *, seed: int = 7, alns_iterations: int = 10, alns_time: float = 0.35) -> dict:
    case = _case_map()[case_id]
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    ctrl = CommitmentSafePredictiveMpc(
        case.instance,
        case.horizon,
        forecast=forecast,
        n_scenarios=2,
        alns_iterations=alns_iterations,
        time_limit_seconds=alns_time,
        seed=seed,
        use_counterfactuals=True,
        use_forecast=True,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    res = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    report = validate_log(case.instance, res.log)
    # Find first bad event by binary-ish prefix checks
    failing_prefix = None
    if not report.ok:
        log = res.log
        lo, hi = 1, len(log)
        while lo < hi:
            mid = (lo + hi) // 2
            r = validate_log(case.instance, log[:mid])
            if r.ok:
                lo = mid + 1
            else:
                hi = mid
        idx = max(0, lo - 1)
        failing_prefix = {
            "index": idx,
            "kind": log[idx].kind if idx < len(log) else None,
            "time": log[idx].time if idx < len(log) else None,
            "vehicle_id": log[idx].vehicle_id if idx < len(log) else None,
            "data": dict(log[idx].data) if idx < len(log) else {},
            "code": report.code,
            "detail": report.detail,
        }
    return {
        "case_id": case_id,
        "replay_ok": report.ok,
        "code": report.code,
        "detail": report.detail,
        "failing_event": failing_prefix,
        "n_decisions": len(res.decisions),
        "completed": sorted(cid for cid, st in res.final_requests.items() if st == "completed"),
        "accepted_unfulfilled": sorted(cid for cid, st in res.final_requests.items() if st == "accepted_unfulfilled"),
    }


def side_by_side_trace(case_id: str, *, seed: int = 7, alns_iterations: int = 10, alns_time: float = 0.35) -> dict:
    """Event-aligned B1 vs predictive MPC on the same plant releases."""
    case = _case_map()[case_id]
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)

    b1_inner = FullValidationAlnsMpc(
        case.instance, case.horizon, iterations=alns_iterations, time_limit_seconds=alns_time, seed=seed
    )
    mpc_inner = CommitmentSafePredictiveMpc(
        case.instance,
        case.horizon,
        forecast=forecast,
        n_scenarios=2,
        alns_iterations=alns_iterations,
        time_limit_seconds=alns_time,
        seed=seed,  # matched seed
        allocation="uniform",
        use_counterfactuals=True,
        use_forecast=True,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    b1_cap = _CapturePair(b1_inner, "b1")
    mpc_cap = _CapturePair(mpc_inner, "predictive")

    b1_res = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=b1_cap,
    )
    mpc_res = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=mpc_cap,
    )
    b1_rep = validate_log(case.instance, b1_res.log)
    mpc_rep = validate_log(case.instance, mpc_res.log)

    # Align by (time, trigger) approximately
    divergences = []
    n = min(len(b1_cap.epochs), len(mpc_cap.epochs))
    first_consequential = None
    for i in range(n):
        a, b = b1_cap.epochs[i], mpc_cap.epochs[i]
        same_legs = a["first_legs"] == b["first_legs"] and a["newly_accepted"] == b["newly_accepted"]
        same_reject = a["rejected"] == b["rejected"]
        if same_legs and same_reject:
            continue
        # consequential if accept/reject/charge/service first leg differs
        row = {
            "epoch_index": i,
            "b1_time": a["time"],
            "mpc_time": b["time"],
            "b1_trigger": a["trigger"],
            "mpc_trigger": b["trigger"],
            "b1": {
                "newly_accepted": a["newly_accepted"],
                "rejected": a["rejected"],
                "first_legs": a["first_legs"],
                "soc": [v["soc"] for v in a["vehicles"]],
                "nodes": [v["node"] for v in a["vehicles"]],
            },
            "mpc": {
                "newly_accepted": b["newly_accepted"],
                "rejected": b["rejected"],
                "first_legs": b["first_legs"],
                "soc": [v["soc"] for v in b["vehicles"]],
                "nodes": [v["node"] for v in b["vehicles"]],
                "n_valid_actions": b.get("n_valid_actions"),
            },
        }
        divergences.append(row)
        if first_consequential is None:
            first_consequential = row

    def summary(res, rep, epochs):
        final = res.final_requests
        return {
            "completed_count": sum(1 for st in final.values() if st == "completed"),
            "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
            "rejected_count": sum(1 for st in final.values() if st == "rejected"),
            "executed_distance": executed_distance_from_log(case.instance, res.log),
            "optimize_seconds": res.optimize_seconds,
            "replay_ok": rep.ok,
            "replay_code": rep.code,
            "replay_detail": rep.detail,
            "n_epochs_recorded": len(epochs),
            "completed": sorted(cid for cid, st in final.items() if st == "completed"),
            "accepted_unfulfilled": sorted(cid for cid, st in final.items() if st == "accepted_unfulfilled"),
        }

    return {
        "case_id": case_id,
        "seed": seed,
        "releases": case.releases,
        "b1": summary(b1_res, b1_rep, b1_cap.epochs),
        "predictive": summary(mpc_res, mpc_rep, mpc_cap.epochs),
        "first_consequential_divergence": first_consequential,
        "n_divergences": len(divergences),
        "divergences": divergences[:40],
        "b1_epochs_head": b1_cap.epochs[:8],
        "mpc_epochs_head": mpc_cap.epochs[:8],
    }


class StickyFirstActionController:
    """Force a fixed first executable decision; then fall back to B1-validated ALNS/insertion path.

    Used to test whether first-action interventions are overwritten by immediate recourse.
    """

    def __init__(self, instance, horizon, forced: Decision, *, seed: int = 7, alns_iterations: int = 10, alns_time: float = 0.2):
        self._forced = forced
        self._used = False
        self._b1 = FullValidationAlnsMpc(
            instance, horizon, iterations=alns_iterations, time_limit_seconds=alns_time, seed=seed
        )
        self.overrides = 0

    def decide(self, observation: Observation, trigger: str) -> Decision:
        if not self._used:
            self._used = True
            # Re-sanitize against current obs
            from safe_time_evrp.mpc_central.counterfactual_actions import sanitize_routes

            routes = sanitize_routes(observation, self._forced.routes)
            return Decision(
                time=observation.time,
                routes=routes,
                accepted=list(self._forced.accepted),
                newly_accepted=list(self._forced.newly_accepted),
                rejected=list(self._forced.rejected),
                deferred=[],
                fallback_used=False,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=list(self._forced.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=0.0,
                trigger=trigger,
                locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
                notes=["sticky_first_action", *list(self._forced.notes)[:3]],
            )
        d = self._b1.decide(observation, trigger)
        self.overrides += 1
        return d


def first_action_matter_tests(case_id: str = "B_phase_b", *, seed: int = 7) -> dict:
    case = _case_map()[case_id]
    # Build initial observation
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        if t <= 0:
            sim.schedule_release(cid, 0.0)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    scenarios = [visible_forecast(obs, forecast, case.horizon, scenario_index=i) for i in range(2)]
    cands, _diag = generate_counterfactual_actions(
        case.instance, obs, horizon=case.horizon, alns_iterations=8, alns_time=0.1, seed=seed, include_b1=True
    )
    by_name = {n: d for n, d in cands}

    pairs = []
    # Pick named interventions if present
    names = []
    if any(n.startswith("accept:") for n in by_name):
        names.append(next(n for n in by_name if n.startswith("accept:")))
    if "wait_idle" in by_name:
        names.append("wait_idle")
    if any(n.startswith("reject:") for n in by_name):
        names.append(next(n for n in by_name if n.startswith("reject:")))
    if any(n.startswith("charge:") for n in by_name):
        names.append(next(n for n in by_name if n.startswith("charge:")))
    if "alns" in by_name:
        names.insert(0, "alns")

    score_rows = []
    for name in names:
        cand = by_name[name]
        mean_v, scores = expected_rollout_value(
            case.instance, obs, cand, scenarios, horizon=case.horizon, max_events=150
        )
        score_rows.append(
            {
                "name": name,
                "mean_value": mean_v,
                "scenario_values": [s.value for s in scores],
                "replay_ok": all(s.replay_ok for s in scores),
                "first_legs": [list(x) for x in FirstActionKey.from_decision(cand).first_legs],
                "newly_accepted": list(cand.newly_accepted),
                "rejected": list(cand.rejected),
            }
        )

    # Sticky plant interventions: hold first action, then B1 recourse on same releases
    sticky_outcomes = []
    for name in names[:4]:
        forced = by_name[name]
        ctrl = StickyFirstActionController(case.instance, case.horizon, forced, seed=seed)
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
        sticky_outcomes.append(
            {
                "forced_name": name,
                "completed_count": sum(1 for st in res.final_requests.values() if st == "completed"),
                "accepted_unfulfilled_count": sum(
                    1 for st in res.final_requests.values() if st == "accepted_unfulfilled"
                ),
                "executed_distance": executed_distance_from_log(case.instance, res.log),
                "replay_ok": rep.ok,
                "replay_code": rep.code,
                "n_subsequent_b1_decisions": ctrl.overrides,
                "first_decision_notes": res.decisions[0].notes if res.decisions else [],
            }
        )

    # Value-tie analysis
    vals = {r["name"]: r["mean_value"] for r in score_rows}
    unique_vals = sorted(set(round(v, 6) for v in vals.values() if v > -1e8))
    sticky_unique = sorted({(o["completed_count"], o["accepted_unfulfilled_count"], round(o["executed_distance"], 4)) for o in sticky_outcomes})
    if len(unique_vals) <= 1 and len(sticky_unique) == 1:
        tie_verdict = "MODELING_ARTIFACT_OR_PERFECT_RECOURSE_CATCHUP"
        tie_reason = (
            "Distinct first actions share equal rollout values and sticky plant outcomes converge — "
            "recourse likely erases first-action differences on this state."
        )
    elif len(unique_vals) <= 1 and len(sticky_unique) > 1:
        tie_verdict = "SCORING_BLIND_BUT_ACTIONS_MATTER"
        tie_reason = "Rollout values tie, but sticky plant outcomes differ — evaluator fails to distinguish consequential actions."
    elif len(unique_vals) > 1 and len(sticky_unique) > 1:
        tie_verdict = "ACTIONS_MATTER"
        tie_reason = "Both predicted values and sticky plant outcomes differ across first actions."
    else:
        tie_verdict = "MIXED"
        tie_reason = "Predicted values differ but sticky outcomes converge (or vice versa)."

    return {
        "case_id": case_id,
        "score_rows": score_rows,
        "sticky_outcomes": sticky_outcomes,
        "tie_verdict": tie_verdict,
        "tie_reason": tie_reason,
    }


def matched_seed_eval(
    case_ids: tuple[str, ...] = FOCUS_CASES,
    *,
    seeds: tuple[int, ...] = (3, 7, 11),
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
                # Fair: identical seed and allocation label for both predictive controllers
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
                    seed=seed,  # MATCHED
                    allocation="uniform",  # MATCHED — no fake allocation difference
                    use_counterfactuals=True,
                    use_forecast=True,
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
                cell["controllers"][name] = {
                    "completed_count": sum(1 for st in final.values() if st == "completed"),
                    "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
                    "executed_distance": executed_distance_from_log(case.instance, res.log),
                    "optimize_seconds": res.optimize_seconds,
                    "replay_ok": rep.ok,
                    "replay_code": rep.code,
                    "replay_detail": rep.detail,
                }
            b1 = cell["controllers"]["b1"]
            prop = cell["controllers"]["proposed_mpc"]
            stoch = cell["controllers"]["stochastic_uniform"]
            cell["paired"] = {
                "proposed_minus_b1_completed": prop["completed_count"] - b1["completed_count"],
                "proposed_minus_b1_au": prop["accepted_unfulfilled_count"] - b1["accepted_unfulfilled_count"],
                "proposed_minus_stoch_completed": prop["completed_count"] - stoch["completed_count"],
                "proposed_opt_minus_b1": prop["optimize_seconds"] - b1["optimize_seconds"],
                "stoch_equals_proposed": (
                    prop["completed_count"] == stoch["completed_count"]
                    and prop["accepted_unfulfilled_count"] == stoch["accepted_unfulfilled_count"]
                    and abs(prop["executed_distance"] - stoch["executed_distance"]) < 1e-9
                ),
                "valid_for_claim": prop["replay_ok"] and b1["replay_ok"],
            }
            rows.append(cell)

    valid = [r for r in rows if r["paired"]["valid_for_claim"]]
    wins = sum(1 for r in valid if r["paired"]["proposed_minus_b1_completed"] > 0 and r["paired"]["proposed_minus_b1_au"] <= 0)
    losses = sum(1 for r in valid if r["paired"]["proposed_minus_b1_completed"] < 0 or r["paired"]["proposed_minus_b1_au"] > 0)
    stoch_eq = sum(1 for r in valid if r["paired"]["stoch_equals_proposed"])
    return {
        "seeds": list(seeds),
        "case_ids": list(case_ids),
        "n_cells": len(rows),
        "n_valid_cells": len(valid),
        "wins_vs_b1_valid": wins,
        "losses_vs_b1_valid": losses,
        "stoch_equals_proposed_valid": stoch_eq,
        "mean_proposed_minus_b1_completed_valid": mean(r["paired"]["proposed_minus_b1_completed"] for r in valid)
        if valid
        else None,
        "rows": rows,
    }


def run_phase3e(*, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or Path("docs/mpc_central")
    out_dir.mkdir(parents=True, exist_ok=True)

    fairness = fairness_contract_report()
    replay_easy = diagnose_replay("B_easy_dynamic")
    dense = side_by_side_trace("A_dense_arrivals")
    low = side_by_side_trace("A_low_soc_charge")
    ties = first_action_matter_tests("B_phase_b")
    matched = matched_seed_eval()

    findings: list[str] = ["EQUIVALENT_TO_STOCHASTIC_ROLLOUT"]

    dense_gain = dense["predictive"]["completed_count"] - dense["b1"]["completed_count"]
    dense_au = dense["predictive"]["accepted_unfulfilled_count"] - dense["b1"]["accepted_unfulfilled_count"]
    # Prior repaired-pilot "dense win" used mismatched seeds; matched-seed trace is authoritative.
    if dense["predictive"]["replay_ok"] and dense["b1"]["replay_ok"]:
        if dense_gain > 0 and dense_au <= 0:
            findings.append("GENUINE_MPC_VALUE_CANDIDATE")
        elif dense_gain < 0:
            findings.append("GENUINE_MPC_FAILURE_CANDIDATE")
            findings.append("EVALUATION_ARTIFACT")  # prior seed-mismatched dense win
    if low["predictive"]["replay_ok"] and low["b1"]["replay_ok"]:
        if low["predictive"]["completed_count"] < low["b1"]["completed_count"]:
            findings.append("GENUINE_MPC_FAILURE_CANDIDATE")
    if not replay_easy["replay_ok"]:
        findings.append("EVALUATION_ARTIFACT")
    if ties.get("tie_verdict") == "ACTIONS_MATTER":
        findings.append("FIRST_ACTIONS_MATTER")
    if matched["stoch_equals_proposed_valid"] == matched["n_valid_cells"] and matched["n_valid_cells"] > 0:
        findings.append("EQUIVALENT_TO_STOCHASTIC_ROLLOUT")
    findings = list(dict.fromkeys(findings))

    if matched["losses_vs_b1_valid"] > matched["wins_vs_b1_valid"] and matched["n_valid_cells"] > 0:
        decision = "GENUINE_MPC_FAILURE"
        reason = (
            "Under matched seeds/budgets, predictive MPC is algorithmically equivalent to stochastic "
            "rollout and is worse than B1 more often than it wins on the focus cases. The earlier "
            "A_dense_arrivals win does not survive matched seeds."
        )
    elif matched["wins_vs_b1_valid"] > matched["losses_vs_b1_valid"]:
        decision = "GENUINE_MPC_VALUE"
        reason = "Valid predictive decisions improve outcomes under matched resources on the focus cases."
    elif "EVALUATION_ARTIFACT" in findings and matched["n_valid_cells"] == 0:
        decision = "EVALUATION_ARTIFACT"
        reason = "Replay/scoring artifacts still dominate; quarantine invalid episodes."
    else:
        decision = "MIXED_OR_EQUIVALENT"
        reason = (
            "No distinct proposed-vs-stochastic mechanism; B1 comparison is mixed or tied after fairness repairs."
        )

    traces = {
        "fairness": fairness,
        "b_easy_dynamic_replay": replay_easy,
        "A_dense_arrivals": dense,
        "A_low_soc_charge": low,
        "first_action_tests": ties,
        "findings": findings,
        "decision": decision,
        "reason": reason,
    }
    (out_dir / "phase3e_decision_traces.json").write_text(json.dumps(traces, indent=2), encoding="utf-8")
    (out_dir / "phase3e_matched_results.json").write_text(json.dumps(matched, indent=2), encoding="utf-8")
    return {"traces": traces, "matched": matched}


if __name__ == "__main__":
    art = run_phase3e()
    print(art["traces"]["decision"], art["traces"]["reason"])
    print(art["matched"]["wins_vs_b1_valid"], art["matched"]["losses_vs_b1_valid"], art["matched"]["stoch_equals_proposed_valid"])
