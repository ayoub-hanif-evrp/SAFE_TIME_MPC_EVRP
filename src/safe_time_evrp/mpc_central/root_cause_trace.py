"""Per-candidate first-decision autopsy for underserving diagnosis."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.forecast import visible_forecast
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey, generate_counterfactual_actions
from safe_time_evrp.mpc_central.phase3d_splits import fit_train_forecast
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, seed_simulator_from_observation


def _initial_obs(case):
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        if t <= 0:
            sim.schedule_release(cid, 0.0)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    return sim.observation()


def trace_first_epoch(case_id: str, *, seed: int = 7, n_scenarios: int = 2) -> dict:
    suite = {c.case_id: c for c in build_baseline_suite()}
    case = suite[case_id]
    obs = _initial_obs(case)
    forecast = fit_train_forecast(n_scenarios=n_scenarios, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    scenarios = [visible_forecast(obs, forecast, case.horizon, scenario_index=i) for i in range(n_scenarios)]
    cands, diag = generate_counterfactual_actions(
        case.instance,
        obs,
        horizon=case.horizon,
        alns_iterations=10,
        alns_time=0.15,
        seed=seed,
        include_b1=True,
    )
    public = make_public_snapshot(case.instance, obs, case.horizon).instance
    b1 = FullValidationAlnsMpc(case.instance, case.horizon, iterations=10, time_limit_seconds=0.15, seed=seed)
    b1_dec = b1.decide(obs, "initial")
    b1_key = FirstActionKey.from_decision(b1_dec)

    # Hypothesis probe: accept without snapshot releases should fail; with seed should pass.
    fork = seed_simulator_from_observation(case.instance, obs)
    probe_kinds = [r.kind for r in fork.log]
    has_releases = any(r.kind == "request_release" for r in fork.log)

    rows = []
    for name, cand in cands:
        nom = validate_continuation(public, obs, cand.routes, require_new=frozenset(cand.newly_accepted))
        mean_v, scores = expected_rollout_value(
            case.instance,
            obs,
            cand,
            scenarios,
            horizon=case.horizon,
            max_events=200,
        )
        key = FirstActionKey.from_decision(cand)
        rows.append(
            {
                "name": name,
                "first_action_key": {
                    "newly_accepted": list(key.newly_accepted),
                    "rejected": list(key.rejected),
                    "first_legs": [list(x) for x in key.first_legs],
                },
                "matches_b1_first_action": key == b1_key,
                "nominal_ok": nom.ok,
                "nominal_reasons": list(nom.reasons)[:3],
                "mean_value": mean_v,
                "any_scenario_invalid": any(not s.replay_ok for s in scores),
                "all_scenarios_minus_1e9": all(s.value <= -1e8 for s in scores),
                "scenarios": [
                    {
                        "value": s.value,
                        "replay_ok": s.replay_ok,
                        "replay_code": s.replay_code,
                        "replay_detail": s.replay_detail,
                        "completed": list(s.completed),
                        "accepted_unfulfilled": list(s.accepted_unfulfilled),
                        "residual_feasible_pending": list(s.residual_feasible_pending),
                        "executed_distance": s.executed_distance,
                        "notes": list(s.notes)[:8],
                    }
                    for s in scores
                ],
            }
        )

    # Rank as controller would (fail-closed mean + service-preferring tie-break).
    def _rank_row(r: dict):
        key = r["first_action_key"]
        n_service = sum(1 for leg in key["first_legs"] if leg[2] == "service")
        not_wait = 0 if str(r["name"]).startswith("wait") else 1
        return (r["mean_value"], len(key["newly_accepted"]), n_service, not_wait, r["name"])

    ranked = sorted(rows, key=_rank_row, reverse=True)
    chosen = ranked[0] if ranked else None
    serve_like = [
        r
        for r in rows
        if r["first_action_key"]["newly_accepted"]
        or any(leg[2] == "service" for leg in r["first_action_key"]["first_legs"])
    ]
    serve_all_invalid = bool(serve_like) and all(r["all_scenarios_minus_1e9"] for r in serve_like)
    early = any(
        sc["replay_code"] == "early_request_access" or "early_request_access" in (sc["replay_detail"] or "")
        for r in rows
        for sc in r["scenarios"]
    )
    b1_rows = [r for r in rows if r["matches_b1_first_action"]]

    if early or (serve_all_invalid and chosen and chosen["mean_value"] <= -1e8):
        verdict = "IMPLEMENTATION_DEFECT_CONFIRMED"
        reason = (
            "early_request_access or invalid serve/accept scores remain after fork seeding."
            if early
            else "Serve/accept candidates still score as invalid after fork seeding."
        )
    elif chosen and chosen["mean_value"] > -1e8 and b1_rows:
        b1_row = b1_rows[0]
        if b1_row["mean_value"] > chosen["mean_value"] + 1e-9:
            verdict = "OBJECTIVE_MISSPECIFICATION"
            reason = "B1 action scores higher than chosen action but was not selected (ranking bug)."
        elif b1_row["mean_value"] + 1e-9 < chosen["mean_value"] and not chosen["matches_b1_first_action"]:
            verdict = "OBJECTIVE_MISSPECIFICATION"
            reason = (
                "Valid rollouts: scorer prefers a non-B1 first action with higher internal value "
                f"(chosen={chosen['name']} value={chosen['mean_value']}, b1_value={b1_row['mean_value']})."
            )
        elif chosen["matches_b1_first_action"]:
            verdict = "OBJECTIVE_MISSPECIFICATION"
            reason = (
                "Fork/replay valid and first action matches B1 at this epoch; "
                "closed-loop underserving (if any) arises later or from objective elsewhere."
            )
        else:
            verdict = "GENUINE_POLICY_FAILURE"
            reason = "Valid scores; chosen action differs from B1 without a clear scoring defect."
    elif not b1_rows:
        verdict = "GENUINE_POLICY_FAILURE"
        reason = "B1 first action missing from candidate set under current generator."
    else:
        verdict = "OBJECTIVE_MISSPECIFICATION"
        reason = "Fork/replay appears valid; inspect value decomposition vs B1 outcomes."

    return {
        "case_id": case_id,
        "observation": {
            "time": obs.time,
            "released_open": list(obs.released_open),
            "accepted": list(obs.accepted),
            "vehicle_statuses": [v.status for v in obs.vehicles],
        },
        "fork_probe": {
            "has_snapshot_request_releases": has_releases,
            "log_kinds_prefix": probe_kinds[:12],
        },
        "b1_first_action": {
            "newly_accepted": list(b1_key.newly_accepted),
            "rejected": list(b1_key.rejected),
            "first_legs": [list(x) for x in b1_key.first_legs],
        },
        "diagnostics": {
            "raw_candidates": diag.raw_candidates,
            "valid_commitment_safe": diag.valid_commitment_safe,
            "distinct_first_actions": diag.distinct_first_actions,
        },
        "candidates": rows,
        "chosen": chosen["name"] if chosen else None,
        "chosen_value": chosen["mean_value"] if chosen else None,
        "verdict": verdict,
        "reason": reason,
    }


def run_root_cause_trace(*, out_path: Path | None = None) -> dict:
    cases = ["B_phase_b", "B_tight_battery"]
    traces = [trace_first_epoch(cid) for cid in cases]
    # Aggregate
    verdicts = {t["verdict"] for t in traces}
    if "IMPLEMENTATION_DEFECT_CONFIRMED" in verdicts:
        overall = "IMPLEMENTATION_DEFECT_CONFIRMED"
    elif "OBJECTIVE_MISSPECIFICATION" in verdicts:
        overall = "OBJECTIVE_MISSPECIFICATION"
    else:
        overall = "GENUINE_POLICY_FAILURE"
    art = {
        "overall_verdict": overall,
        "hypothesis": (
            "seed_simulator_from_observation omitted request_release history → "
            "validate_log early_request_access → accept/serve scored -1e9"
        ),
        "traces": traces,
    }
    path = out_path or Path("docs/mpc_central/root_cause_trace.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(art, indent=2), encoding="utf-8")
    return art


if __name__ == "__main__":
    art = run_root_cause_trace()
    print(art["overall_verdict"])
    for t in art["traces"]:
        print(t["case_id"], t["verdict"], t["chosen"], t["chosen_value"], t["reason"][:100])
