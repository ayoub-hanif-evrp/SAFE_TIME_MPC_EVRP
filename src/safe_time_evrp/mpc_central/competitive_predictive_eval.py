"""Controlled development + one independent final comparison for BAP-CCE.

Compares against greedy-nominal incumbent (strong reference), not only B1.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    PROTOCOL_VERSION_V2,
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    calibration_report_finite_vs_poisson,
    fit_finite_demand_model,
)
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey, generate_counterfactual_actions
from safe_time_evrp.mpc_central.forecast_stall_diagnostic import DIAGNOSTIC_STEMS
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
ALNS_TIME = 0.35
N_SCENARIOS = 2
ENV_REALIZATIONS_DEV = 2
SOURCE_SHA_BASELINE = "442a42329d283bad14f1900eac6a37ab33b6e0cb"


def _summarize(case, name: str, result, ctrl, *, wall: float, failure: str | None = None) -> dict:
    if failure:
        return {
            "controller": name,
            "failure": failure,
            "wall_seconds": wall,
            "completed_count": None,
            "replay_ok": False,
        }
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    rejected = sum(1 for st in final.values() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
    return {
        "controller": name,
        "failure": None if rep.ok else f"replay_invalid:{rep.code}",
        "completed_count": completed,
        "accepted_unfulfilled_count": au,
        "rejected_count": rejected,
        "executed_distance": dist,
        "service_per_distance": (completed / dist) if dist and dist > 1e-9 else None,
        "optimize_seconds": result.optimize_seconds,
        "wall_seconds": wall,
        "termination_reason": result.termination_reason,
        "replay_ok": rep.ok,
        "replay_code": rep.code,
        "certificate_status_last": getattr(ctrl, "last_validation_status", None),
        "deadline_overruns": getattr(getattr(ctrl, "profile", None), "deadline_overruns", None),
        "n_decisions": len(result.decisions),
        "fallback_count": result.fallback_count,
    }


def _run(case, ctrl, name: str) -> dict:
    t0 = time.perf_counter()
    try:
        result = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
        )
        return _summarize(case, name, result, ctrl, wall=time.perf_counter() - t0)
    except Exception as exc:  # noqa: BLE001
        return _summarize(case, name, None, ctrl, wall=time.perf_counter() - t0, failure=f"{type(exc).__name__}:{exc}")


def _controllers(case, *, arrival, finite, pol: int, budget: float):
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=budget,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=120,
    )
    return {
        "b1": FullValidationAlnsMpc(
            case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol
        ),
        "m1": CertificateCarryingAlnsMpc(
            case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol
        ),
        "cce_greedy_nominal": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="greedy_nominal",
            **common,
        ),
        "cce_causal_empty_future": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="causal",
            **common,
        ),
        "cce_conditional_poisson": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCENARIOS,
            use_forecast=True,
            use_persistent_certificate=True,
            scoring_mode="causal",
            conditional_forecast=True,
            announcement_mean=6.12,
            **common,
        ),
        "cce_finite_demand": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCENARIOS,
            use_forecast=True,
            use_persistent_certificate=True,
            scoring_mode="causal",
            use_finite_demand=True,
            finite_demand_model=finite,
            **common,
        ),
        "bap_cce": BaselineAnchoredPredictiveCCE(
            case.instance,
            case.horizon,
            forecast=arrival,
            finite_model=finite,
            n_scenarios=N_SCENARIOS,
            use_finite_demand=True,
            **common,
        ),
        "stochastic_finite": CommitmentSafePredictiveMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCENARIOS,
            use_counterfactuals=True,
            use_forecast=True,
            allocation="uniform",
            **common,
        ),
    }


def restricted_hindsight_opportunity(case, *, seed: int, finite) -> dict:
    """Offline: best restricted first action vs greedy-nominal under realized futures."""
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    from safe_time_evrp.mpc3c.forecast import ForecastCustomer

    future = []
    for cid, t in case.releases:
        if t <= obs.time + 1e-12:
            continue
        node = case.instance.node(cid)
        future.append(
            ForecastCustomer(
                customer_id=f"hindsight_{cid}",
                ready_time=float(node.window.ready),
                due_time=float(node.window.due),
                x=float(node.x),
                y=float(node.y),
                demand=float(node.demand),
                service_time=float(node.service_time),
                announcement_time=float(t),
                source="hindsight_offline_only",
            )
        )
    incumb = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        n_scenarios=1,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=seed,
        use_forecast=False,
        scoring_mode="greedy_nominal",
        use_persistent_certificate=True,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=120,
    )
    d_inc = incumb.decide(obs, "initial")
    candidates, _ = generate_counterfactual_actions(
        case.instance,
        obs,
        horizon=case.horizon,
        alns_iterations=ALNS_ITER,
        alns_time=0.15,
        seed=seed,
        include_solver_baselines=True,
        include_b1=True,
    )
    named = [("incumbent", d_inc)] + list(candidates)[:8]
    scenarios = [future]
    best_name, best_v, inc_v = None, -1e18, None
    for name, cand in named:
        v, scores = expected_rollout_value(
            case.instance,
            obs,
            cand,
            scenarios,
            horizon=case.horizon,
            scoring_mode="causal",
            max_replan_interval=case.max_replan_interval,
            max_events=120,
        )
        if not scores or not scores[0].replay_ok:
            continue
        if name == "incumbent":
            inc_v = v
        if v > best_v:
            best_v, best_name = v, name
    improves = (
        inc_v is not None
        and best_v is not None
        and best_name != "incumbent"
        and FirstActionKey.from_decision(next(c for n, c in named if n == best_name))
        != FirstActionKey.from_decision(d_inc)
        and best_v > inc_v + 1e-6
    )
    return {
        "label": "restricted_hindsight_opportunity_offline",
        "n_future": len(future),
        "incumbent_value": inc_v,
        "best_name": best_name,
        "best_value": best_v,
        "hindsight_improves_on_incumbent": bool(improves),
        "delta": (None if inc_v is None or best_v is None else best_v - inc_v),
        "note": "Offline only; realized futures never enter online decide().",
    }


def _mean(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "mean": None}
    m = sum(xs) / len(xs)
    if len(xs) == 1:
        return {"n": 1, "mean": m, "std": 0.0}
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return {"n": len(xs), "mean": m, "std": var**0.5}


def _paired(rows: list[dict], a: str, b: str) -> dict:
    deltas = []
    wins = {"better": 0, "worse": 0, "tie": 0}
    for row in rows:
        ca, cb = row["controllers"].get(a), row["controllers"].get(b)
        if not ca or not cb or ca.get("completed_count") is None or cb.get("completed_count") is None:
            continue
        d = ca["completed_count"] - cb["completed_count"]
        deltas.append(d)
        if d > 0:
            wins["better"] += 1
        elif d < 0:
            wins["worse"] += 1
        else:
            wins["tie"] += 1
    return {"completed_delta": _mean(deltas), "tally": wins}


def run_phase(
    *,
    stems: list[str],
    split_prefer: dict[str, str],
    env_xor: int,
    n_realizations: int,
    budget: float,
    arrival,
    finite,
    include_hindsight: bool,
) -> list[dict]:
    rows = []
    for stem in stems:
        split = split_prefer.get(stem, "development")
        for ridx in range(n_realizations):
            env = (environment_seed_for(stem, ridx) ^ env_xor) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, classifications, fleet_meta = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split=split
            )
            case = episode.case
            cell = {
                "stem": stem,
                "split": split,
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "fleet_meta": fleet_meta,
                "n_late": sum(1 for c in classifications if c.late_for_depot_admit),
                "controllers": {},
            }
            if include_hindsight:
                cell["hindsight_opportunity"] = restricted_hindsight_opportunity(case, seed=pol, finite=finite)
            for name, ctrl in _controllers(case, arrival=arrival, finite=finite, pol=pol, budget=budget).items():
                cell["controllers"][name] = _run(case, ctrl, name)
            rows.append(cell)
    return rows


def conclude(dev_rows: list[dict], final_rows: list[dict] | None) -> dict:
    paired_bap_vs_gn = _paired(dev_rows, "bap_cce", "cce_greedy_nominal")
    paired_fd_vs_gn = _paired(dev_rows, "cce_finite_demand", "cce_greedy_nominal")
    paired_bap_vs_b1 = _paired(dev_rows, "bap_cce", "b1")
    final_note = None
    if final_rows:
        final_note = {
            "bap_vs_greedy_nominal": _paired(final_rows, "bap_cce", "cce_greedy_nominal"),
            "bap_vs_b1": _paired(final_rows, "bap_cce", "b1"),
        }
    d = paired_bap_vs_gn["completed_delta"].get("mean")
    tally = paired_bap_vs_gn["tally"]
    if d is None:
        label = "inconclusive"
        reason = "No paired development cells."
    elif final_rows and final_note:
        fd = final_note["bap_vs_greedy_nominal"]["completed_delta"].get("mean")
        ft = final_note["bap_vs_greedy_nominal"]["tally"]
        if fd is not None and fd > 0.5 and ft["better"] > ft["worse"] + 1:
            label = "predictive_outperforms_strong_incumbent_on_held_out"
            reason = f"Final held-out mean delta BAP-GN ~ {fd:.3f}; tally={ft}."
        elif fd is not None and fd < -0.25 and ft["worse"] >= ft["better"]:
            label = "greedy_nominal_remains_strongest_empirical_contribution"
            reason = (
                f"Final held-out BAP did not beat greedy-nominal (delta~{fd:.3f}, tally={ft}). "
                "Recommend nominal CC-E as strongest empirical result; predictive superiority not shown."
            )
        else:
            label = "technically_complete_negative_or_incremental"
            reason = f"Final held-out inconclusive/incremental (delta~{fd}, tally={ft})."
    elif d > 0.5 and tally["better"] > tally["worse"] + 1:
        label = "dev_only_predictive_gain_unconfirmed"
        reason = f"Development suggests gain (delta~{d:.3f}) but no held-out confirmation in this run."
    elif d < -0.25 and tally["worse"] >= tally["better"]:
        label = "greedy_nominal_remains_strongest_empirical_contribution"
        reason = (
            f"On development, BAP does not beat greedy-nominal (delta~{d:.3f}, tally={tally}). "
            "Predictive superiority not demonstrated."
        )
    else:
        label = "technically_complete_negative_or_incremental"
        reason = f"Development mixed/incremental vs greedy-nominal (delta~{d}, tally={tally})."
    return {
        "label": label,
        "reason": reason,
        "dev_bap_vs_greedy_nominal": paired_bap_vs_gn,
        "dev_finite_vs_greedy_nominal": paired_fd_vs_gn,
        "dev_bap_vs_b1": paired_bap_vs_b1,
        "final": final_note,
    }


def run_all(*, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or Path("docs/experiments")
    splits = stratified_split_small()
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    calib = calibration_report_finite_vs_poisson(finite=finite, poisson_mu=6.12, n_realizations=2)

    # Development: predeclared diagnostic stems excluding pure test.
    dev_stems = [s for s in DIAGNOSTIC_STEMS if s not in splits["test"]]
    split_map = {s: ("train" if s in splits["train"] else "development") for s in dev_stems}
    t0 = time.perf_counter()
    dev_rows = run_phase(
        stems=dev_stems,
        split_prefer=split_map,
        env_xor=0xA5A5A5,
        n_realizations=ENV_REALIZATIONS_DEV,
        budget=ALNS_TIME,
        arrival=arrival,
        finite=finite,
        include_hindsight=True,
    )
    # ONE independent final eval on preregistered test stems, fresh env XOR.
    final_stems = list(splits["test"])[:6]  # C/R/RC mix in stratified test; keep small
    final_map = {s: "test" for s in final_stems}
    final_rows = run_phase(
        stems=final_stems,
        split_prefer=final_map,
        env_xor=0x5A5A17,  # fresh relative to diagnostic
        n_realizations=1,
        budget=ALNS_TIME,
        arrival=arrival,
        finite=finite,
        include_hindsight=False,
    )
    # Opportunity summary
    opp = [r["hindsight_opportunity"] for r in dev_rows if r.get("hindsight_opportunity") is not None]
    n_imp = sum(1 for o in opp if o.get("hindsight_improves_on_incumbent"))
    summary = {
        "completed_by_controller_dev": {},
        "opportunity": {
            "n_epochs_checked": len(opp),
            "n_hindsight_improves": n_imp,
            "rate": (n_imp / len(opp)) if opp else None,
        },
    }
    by = {}
    for row in dev_rows:
        for name, cell in row["controllers"].items():
            if cell.get("completed_count") is not None:
                by.setdefault(name, []).append(float(cell["completed_count"]))
    summary["completed_by_controller_dev"] = {k: _mean(v) for k, v in by.items()}
    decision = conclude(dev_rows, final_rows)
    payload = {
        "protocol_version": PROTOCOL_VERSION_V2,
        "mission": "baseline_anchored_predictive_competitive",
        "archived_baseline_sha": SOURCE_SHA_BASELINE,
        "alns_iterations": ALNS_ITER,
        "time_limit_seconds": ALNS_TIME,
        "calibration_finite_vs_poisson": {k: calib[k] for k in calib if k != "rows"},
        "calibration_rows_sample": calib["rows"][:6],
        "development_stems": dev_stems,
        "final_stems": final_stems,
        "summary": summary,
        "decision": decision,
        "development_rows": dev_rows,
        "final_rows": final_rows,
        "wall_seconds_total": time.perf_counter() - t0,
        "reproducibility": ("python -m safe_time_evrp.mpc_central.competitive_predictive_eval"),
        "limitation": (
            "Base Schneider instances appeared in earlier experiments; fresh environment "
            "seeds do not make them completely unseen instances. Cooperative time limits "
            "are not hard-preemptive for noninterruptible ALNS calls."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FINAL_COMPETITIVE_COMPARISON.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "FINITE_DEMAND_FORECAST_CALIBRATION.md").write_text(_calib_md(calib), encoding="utf-8")
    (out_dir / "PREDICTIVE_OPPORTUNITY_AND_ACTION_AUDIT.md").write_text(_opp_md(payload), encoding="utf-8")
    (out_dir / "FINAL_COMPETITIVE_COMPARISON.md").write_text(_final_md(payload), encoding="utf-8")
    return payload


def _calib_md(calib: dict) -> str:
    return "\n".join(
        [
            "# Finite-demand forecast calibration",
            "",
            f"**Protocol:** `{calib['protocol_version']}`",
            "",
            f"- Sum realized dynamic arrivals (dev segments): **{calib['sum_realized']:.2f}**",
            f"- Sum predicted (finite model): **{calib['sum_predicted_finite']:.2f}** "
            f"(ratio {calib['finite_over_realized_ratio']:.3f})",
            f"- Sum predicted (old Poisson-over-horizon): **{calib['sum_predicted_poisson']:.2f}** "
            f"(ratio {calib['poisson_over_realized_ratio']:.3f})",
            "",
            calib["note"],
            "",
            "A successful correction requires the finite ratio near 1 and far below the "
            "Poisson over-prediction ratio — not merely a re-fit of μ.",
            "",
        ]
    )


def _opp_md(payload: dict) -> str:
    s = payload["summary"]["opportunity"]
    return "\n".join(
        [
            "# Predictive opportunity and action audit",
            "",
            "Restricted offline hindsight on the same feasible candidate set as online "
            "control (realized futures offline only).",
            "",
            f"- Epochs checked: **{s['n_epochs_checked']}**",
            f"- Hindsight improves on greedy-nominal incumbent: **{s['n_hindsight_improves']}** (rate={s['rate']})",
            "",
            "If hindsight rarely improves, the candidate set offers little exploitable "
            "predictive opportunity. If hindsight helps but online forecast does not, "
            "attribute error to the model or ranking/compute — not to 'no value of information' "
            "in the abstract.",
            "",
            "See `FINAL_COMPETITIVE_COMPARISON.json` → `development_rows[*].hindsight_opportunity`.",
            "",
        ]
    )


def _final_md(payload: dict) -> str:
    d = payload["decision"]
    return "\n".join(
        [
            "# Final competitive comparison",
            "",
            f"**Archived baseline SHA:** `{payload['archived_baseline_sha']}`",
            f"**Protocol:** `{payload['protocol_version']}`",
            f"**Wall seconds:** {payload['wall_seconds_total']}",
            "",
            "## Decision",
            "",
            f"**{d['label']}**",
            "",
            d["reason"],
            "",
            "## Development completed means",
            "",
            f"```json\n{json.dumps(payload['summary']['completed_by_controller_dev'], indent=2)}\n```",
            "",
            "## Paired vs greedy-nominal (development)",
            "",
            f"```json\n{json.dumps(d['dev_bap_vs_greedy_nominal'], indent=2)}\n```",
            "",
            "## Held-out final",
            "",
            f"```json\n{json.dumps(d.get('final'), indent=2)}\n```",
            "",
            "## Limitations",
            "",
            payload["limitation"],
            "",
            f"Reproduce: `{payload['reproducibility']}`",
            "",
        ]
    )


def main() -> None:
    payload = run_all()
    print(json.dumps({"decision": payload["decision"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
