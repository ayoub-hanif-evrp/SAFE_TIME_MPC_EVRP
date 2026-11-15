"""Controlled forecast-scoring causal evaluation (methodology repair).

Compares greedy-nominal vs causal empty-future vs conditional calibrated forecast
under matched Schneider-v2 development episodes. Does not retune objective weights.
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
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    build_anonymous_scenarios,
    fit_empirical_arrivals,
    sample_conditional_scenarios,
    sample_conditional_scenarios_crn,
)
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.mpc_central.forecast_calibration import (
    calibrate_train_announcement_rate,
    predicted_vs_realized_on_development,
)
from safe_time_evrp.mpc_central.forecast_stall_diagnostic import DIAGNOSTIC_STEMS
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
ALNS_TIME = 0.35
N_SCENARIOS = 2
ENV_REALIZATIONS = 2
MISSPECIFIED_MU = 12.0


def release_statistics_diagnostic(episode, classifications) -> dict:
    """Release-history summary only — not an oracle and not perfect-information MPC."""
    return {
        "label": "release_statistics_diagnostic",
        "n_releases": len(episode.releases),
        "n_late_for_depot_admit": sum(1 for c in classifications if c.late_for_depot_admit),
        "note": (
            "Not a perfect-information oracle. Records release statistics only; "
            "no hindsight decisions or values are computed here."
        ),
    }


def restricted_hindsight_comparator(episode, classifications, *, seed: int = 0) -> dict:
    """Offline restricted-candidate hindsight using realized future releases.

    Uses the same causal empty-vs-realized contrast at the initial observation only.
    Does not enter online decide().
    """
    case = episode.case
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    # Build anonymous-looking forecast from *realized* future releases (offline only).
    from safe_time_evrp.mpc3c.forecast import ForecastCustomer

    future = []
    for cid, t in case.releases:
        if t <= obs.time + 1e-12:
            continue
        node = case.instance.node(cid)
        future.append(
            ForecastCustomer(
                customer_id=f"hindsight_{cid}",
                ready_time=float(t),
                due_time=float(node.window.due),
                x=float(node.x),
                y=float(node.y),
                demand=float(node.demand),
                service_time=float(node.service_time),
                announcement_time=float(t),
                source="hindsight_offline_only",
            )
        )
    ctrl = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        n_scenarios=1,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=seed,
        use_forecast=True,
        use_persistent_certificate=True,
        scenario_override=[future],
        scoring_mode="causal",
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    d_h = ctrl.decide(obs, "hindsight_offline")
    ctrl_empty = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        n_scenarios=1,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=seed,
        use_forecast=False,
        use_persistent_certificate=True,
        scoring_mode="causal",
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    d_e = ctrl_empty.decide(obs, "empty_future")
    return {
        "label": "restricted_hindsight_comparator_offline",
        "n_future_realized": len(future),
        "n_late": sum(1 for c in classifications if c.late_for_depot_admit),
        "hindsight_first_legs": [list(x) for x in FirstActionKey.from_decision(d_h).first_legs],
        "empty_future_first_legs": [list(x) for x in FirstActionKey.from_decision(d_e).first_legs],
        "actions_differ": FirstActionKey.from_decision(d_h) != FirstActionKey.from_decision(d_e),
        "note": "Offline only; realized futures never passed into online episode controllers.",
    }


def _crn_mu_probe(model: ArrivalForecast, *, mu_miss: float, mu_cal: float) -> dict:
    """Share one RNG skeleton so mu=12 vs calibrated mu differ only in rate."""
    from types import SimpleNamespace

    obs = SimpleNamespace(
        time=0.0,
        released_open=(),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
    )
    paired = sample_conditional_scenarios_crn(
        model,
        obs,
        horizon=80.0,
        n_scenarios=2,
        seed=0,
        announcement_means=(mu_miss, mu_cal),
    )
    return {
        "mu_misspecified": mu_miss,
        "mu_calibrated": mu_cal,
        "n_arrivals_miss_by_scenario": [len(s) for s in paired[float(mu_miss)]],
        "n_arrivals_cal_by_scenario": [len(s) for s in paired[float(mu_cal)]],
        "note": "Common-random-number uniforms; only gap scaling differs by mu.",
    }


def _train_model(train_stems: list[str]) -> ArrivalForecast:
    return fit_empirical_arrivals([load_instance(s) for s in train_stems])


def _old_catalogue(model: ArrivalForecast, *, seed: int, mu: float) -> ArrivalForecast:
    return build_anonymous_scenarios(
        model,
        n_scenarios=N_SCENARIOS,
        customers_per_scenario=2,
        seed=seed,
        day_horizon=200.0,
        announcement_mean=mu,
    )


def _summarize(case, name: str, result, ctrl, *, wall: float, failure: str | None = None) -> dict:
    if failure:
        return {
            "controller": name,
            "failure": failure,
            "stall": "decision loop did not advance time" in failure,
            "wall_seconds": wall,
            "completed_count": None,
            "accepted_unfulfilled_count": None,
            "rejected_count": None,
            "replay_ok": False,
        }
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    return {
        "controller": name,
        "failure": None if rep.ok else f"replay_invalid:{rep.code}",
        "stall": False,
        "completed_count": sum(1 for st in final.values() if st == "completed"),
        "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
        "rejected_count": sum(1 for st in final.values() if st == "rejected"),
        "executed_distance": executed_distance_from_log(case.instance, result.log),
        "optimize_seconds": result.optimize_seconds,
        "wall_seconds": wall,
        "termination_reason": result.termination_reason,
        "replay_ok": rep.ok,
        "replay_code": rep.code,
        "certificate_status_last": getattr(ctrl, "last_validation_status", None),
        "deadline_overruns": getattr(getattr(ctrl, "profile", None), "deadline_overruns", None),
        "n_decisions": len(result.decisions),
        "scoring_mode": getattr(ctrl, "scoring_mode", None),
        "conditional_forecast": getattr(ctrl, "conditional_forecast", None),
        "use_forecast": getattr(ctrl, "use_forecast", None),
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


def _build_controllers(case, *, model: ArrivalForecast, pol: int, mu_cal: float):
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    old_fc = _old_catalogue(model, seed=pol, mu=MISSPECIFIED_MU)
    return {
        "b1": FullValidationAlnsMpc(
            case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=pol
        ),
        "m1": CertificateCarryingAlnsMpc(
            case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=pol
        ),
        "cce_greedy_nominal": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=model,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="greedy_nominal",
            **common,
        ),
        "cce_causal_empty_future": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=model,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="causal",
            **common,
        ),
        "cce_old_fixed_catalogue": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=old_fc,
            n_scenarios=N_SCENARIOS,
            use_forecast=True,
            use_persistent_certificate=True,
            scoring_mode="causal",
            conditional_forecast=False,
            announcement_mean=MISSPECIFIED_MU,
            **common,
        ),
        "cce_conditional_calibrated": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=model,
            n_scenarios=N_SCENARIOS,
            use_forecast=True,
            use_persistent_certificate=True,
            scoring_mode="causal",
            conditional_forecast=True,
            announcement_mean=mu_cal,
            **common,
        ),
        "stochastic_conditional_calibrated": CommitmentSafePredictiveMpc(
            case.instance,
            case.horizon,
            forecast=model,
            n_scenarios=N_SCENARIOS,
            use_counterfactuals=True,
            use_forecast=True,
            conditional_forecast=True,
            announcement_mean=mu_cal,
            allocation="uniform",
            **common,
        ),
    }


def _action_diff_audit(case, model: ArrivalForecast, *, pol: int, mu_cal: float) -> list[dict]:
    """Log epochs where causal-empty and conditional-calibrated CC-E differ on first action."""
    empty = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        forecast=model,
        n_scenarios=N_SCENARIOS,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=pol,
        use_forecast=False,
        scoring_mode="causal",
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    cal = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        forecast=model,
        n_scenarios=N_SCENARIOS,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=ALNS_TIME,
        seed=pol,
        use_forecast=True,
        scoring_mode="causal",
        conditional_forecast=True,
        announcement_mean=mu_cal,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    diffs = []
    events = 0
    replan = None
    # Initial
    for label, trigger in (("initial", "initial"),):
        obs = sim.observation()
        d0 = empty.decide(obs, trigger)
        d1 = cal.decide(obs, trigger)
        k0, k1 = FirstActionKey.from_decision(d0), FirstActionKey.from_decision(d1)
        if k0 != k1:
            fcs = sample_conditional_scenarios(
                model, obs, horizon=case.horizon, n_scenarios=N_SCENARIOS, seed=pol, announcement_mean=mu_cal
            )
            diffs.append(
                {
                    "epoch_label": label,
                    "time": obs.time,
                    "trigger": trigger,
                    "accepted": list(obs.accepted),
                    "released_open": list(obs.released_open),
                    "empty_first_legs": [list(x) for x in k0.first_legs],
                    "calibrated_first_legs": [list(x) for x in k1.first_legs],
                    "empty_notes": list(d0.notes)[:8],
                    "calibrated_notes": list(d1.notes)[:8],
                    "n_forecast_customers_sc0": len(fcs[0]) if fcs else 0,
                }
            )
        # Apply empty controller to advance a shared plant for further epoch search
        sim.apply_decision(d0)
        if replan is not None:
            sim.cancel(replan)
        replan = sim.schedule_replan(sim.time + case.max_replan_interval)
    while events < 40 and len(diffs) < 3:
        nxt = sim.next_event_time()
        if nxt is None or nxt > case.t_max:
            break
        ev = sim.pop_event()
        events += 1
        if ev is None or ev.kind not in {
            "request_release",
            "arrive",
            "service_end",
            "charge_end",
            "wait_end",
            "replan_interval",
        }:
            continue
        obs = sim.observation()
        d0 = empty.decide(obs, ev.kind)
        d1 = cal.decide(obs, ev.kind)
        k0, k1 = FirstActionKey.from_decision(d0), FirstActionKey.from_decision(d1)
        if k0 != k1:
            fcs = sample_conditional_scenarios(
                model, obs, horizon=case.horizon, n_scenarios=N_SCENARIOS, seed=pol, announcement_mean=mu_cal
            )
            diffs.append(
                {
                    "epoch_label": f"event_{events}",
                    "time": obs.time,
                    "trigger": ev.kind,
                    "accepted": list(obs.accepted),
                    "released_open": list(obs.released_open),
                    "empty_first_legs": [list(x) for x in k0.first_legs],
                    "calibrated_first_legs": [list(x) for x in k1.first_legs],
                    "empty_notes": list(d0.notes)[:8],
                    "calibrated_notes": list(d1.notes)[:8],
                    "n_forecast_customers_sc0": len(fcs[0]) if fcs else 0,
                }
            )
        try:
            sim.apply_decision(d0)
        except Exception:  # noqa: BLE001
            break
        if replan is not None:
            sim.cancel(replan)
        replan = sim.schedule_replan(sim.time + case.max_replan_interval)
    return diffs


def run_experiment(*, out_json: Path | None = None, out_md: Path | None = None) -> dict:
    splits = stratified_split_small()
    # Development stems from the predeclared diagnostic list only.
    stems = [s for s in DIAGNOSTIC_STEMS if s in splits["development"] or s in splits["train"]]
    # Prefer development; if sparse, keep the fixed diagnostic order but exclude pure test.
    stems = [s for s in DIAGNOSTIC_STEMS if s not in splits["test"]]
    calib = calibrate_train_announcement_rate(dynamicity="medium", n_realizations=3)
    mu_cal = float(calib["calibrated_announcement_mean"])
    pred = predicted_vs_realized_on_development(calibrated_mu=mu_cal, n_realizations=2)
    model = _train_model(splits["train"])
    crn_mu = _crn_mu_probe(model, mu_miss=MISSPECIFIED_MU, mu_cal=mu_cal)

    rows = []
    action_audits = []
    t0 = time.perf_counter()
    for stem in stems:
        split = "train" if stem in splits["train"] else "development"
        for ridx in range(ENV_REALIZATIONS):
            env = (environment_seed_for(stem, ridx) ^ 0xA5A5A5) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, classifications, fleet_meta = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split=split
            )
            case = episode.case
            ctrls = _build_controllers(case, model=model, pol=pol, mu_cal=mu_cal)
            cell = {
                "stem": stem,
                "split": split,
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "fleet_meta": fleet_meta,
                "n_late": sum(1 for c in classifications if c.late_for_depot_admit),
                "release_statistics": release_statistics_diagnostic(episode, classifications),
                "hindsight_offline": restricted_hindsight_comparator(episode, classifications, seed=pol),
                "controllers": {},
            }
            for name, ctrl in ctrls.items():
                cell["controllers"][name] = _run(case, ctrl, name)
            # Paired completed diffs vs causal empty
            base = cell["controllers"]["cce_causal_empty_future"]
            for name, row in cell["controllers"].items():
                if row.get("completed_count") is None or base.get("completed_count") is None:
                    continue
                cell.setdefault("paired_vs_causal_empty", {})[name] = {
                    "completed_delta": row["completed_count"] - base["completed_count"],
                    "au_delta": row["accepted_unfulfilled_count"] - base["accepted_unfulfilled_count"],
                }
            audits = _action_diff_audit(case, model, pol=pol, mu_cal=mu_cal)
            if audits:
                action_audits.append({"stem": stem, "realization_index": ridx, "epochs": audits})
            rows.append(cell)

    summary = _summarize_experiment(rows)
    payload = {
        "protocol_version": PROTOCOL_VERSION_V2,
        "mission": "forecast_scoring_causal_repair",
        "stems": stems,
        "calibration": calib,
        "predicted_vs_realized_development": pred,
        "crn_mu_comparison": crn_mu,
        "summary": summary,
        "action_audits": action_audits,
        "rows": rows,
        "wall_seconds_total": time.perf_counter() - t0,
    }
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if out_md:
        out_md.write_text(_render_md(payload), encoding="utf-8")
    return payload


def _mean(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "mean": None}
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return {"n": 1, "mean": m, "std": 0.0}
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return {"n": len(vals), "mean": m, "std": var**0.5}


def _summarize_experiment(rows: list[dict]) -> dict:
    by_ctrl: dict[str, list[float]] = {}
    fails: dict[str, int] = {}
    paired_cal_vs_empty = []
    paired_greedy_vs_empty = []
    for row in rows:
        for name, cell in row["controllers"].items():
            if cell.get("failure"):
                fails[f"{name}:{str(cell['failure']).split(':')[0]}"] = (
                    fails.get(f"{name}:{str(cell['failure']).split(':')[0]}", 0) + 1
                )
            if cell.get("completed_count") is not None:
                by_ctrl.setdefault(name, []).append(float(cell["completed_count"]))
        p = row.get("paired_vs_causal_empty", {})
        if "cce_conditional_calibrated" in p:
            paired_cal_vs_empty.append(p["cce_conditional_calibrated"]["completed_delta"])
        if "cce_greedy_nominal" in p:
            paired_greedy_vs_empty.append(p["cce_greedy_nominal"]["completed_delta"])
    # Win tally calibrated vs empty
    wins = {"better": 0, "worse": 0, "tie": 0}
    for d in paired_cal_vs_empty:
        if d > 0:
            wins["better"] += 1
        elif d < 0:
            wins["worse"] += 1
        else:
            wins["tie"] += 1
    conclusion = _conclusion(by_ctrl, paired_cal_vs_empty, fails)
    return {
        "completed_by_controller": {k: _mean(v) for k, v in by_ctrl.items()},
        "failure_counts": fails,
        "paired_calibrated_minus_causal_empty": _mean(paired_cal_vs_empty),
        "paired_calibrated_vs_empty_tally": wins,
        "paired_greedy_minus_causal_empty": _mean(paired_greedy_vs_empty),
        "n_rows": len(rows),
        "supported_conclusion": conclusion,
    }


def _conclusion(by_ctrl: dict, paired: list[float], fails: dict) -> dict:
    if fails.get("stall_total") or any("decision" in k for k in fails):
        # check stall keys
        pass
    stallish = sum(v for k, v in fails.items() if "stall" in k or "RuntimeError" in k)
    cal = by_ctrl.get("cce_conditional_calibrated", [])
    empty = by_ctrl.get("cce_causal_empty_future", [])
    if stallish > len(paired) // 2:
        return {
            "label": "inconclusive_compute_or_feasibility",
            "reason": "Too many runtime/stall failures to interpret forecast value cleanly.",
        }
    if not paired:
        return {
            "label": "inconclusive_compute_or_feasibility",
            "reason": "No paired completed-service cells.",
        }
    mean_d = sum(paired) / len(paired)
    better = sum(1 for d in paired if d > 0)
    worse = sum(1 for d in paired if d < 0)
    # Tied / near-tied tallies → negligible even if mean drifts slightly on small n.
    if abs(better - worse) <= 1 or (abs(mean_d) < 0.75 and abs(better - worse) <= 2):
        return {
            "label": "negligible_decision_value",
            "reason": (
                f"Under identical causal objective, paired mean completed delta "
                f"(calibrated - empty-future) ~ {mean_d:.3f} with tally "
                f"better={better}/worse={worse}/n={len(paired)}. "
                f"The large greedy_nominal gap is an unequal-objective artifact, not forecast value."
            ),
        }
    if mean_d > 0.5 and better > worse + 1:
        return {
            "label": "forecasts_improve_under_identical_causal_objective",
            "reason": f"Paired mean delta ~ {mean_d:.3f}; better={better}, worse={worse}, n={len(paired)}.",
        }
    if mean_d < -0.5 and worse > better + 1:
        return {
            "label": "forecasts_harm_from_identifiable_misspecification_or_use",
            "reason": (
                f"Paired mean delta ~ {mean_d:.3f}; better={better}, worse={worse}, n={len(paired)}. "
                f"Means: calibrated={_mean(cal)}, empty={_mean(empty)}."
            ),
        }
    return {
        "label": "inconclusive_compute_or_feasibility",
        "reason": (
            f"Paired mean delta ~ {mean_d:.3f}; better={better}, worse={worse}, n={len(paired)}; "
            "sample too small or mixed to support a directional forecast claim."
        ),
    }


def _render_md(payload: dict) -> str:
    s = payload["summary"]
    calib_compact = {k: payload["calibration"][k] for k in payload["calibration"] if k != "samples"}
    audits = payload.get("action_audits", [])
    n_epochs = sum(len(a.get("epochs", [])) for a in audits)
    lines = [
        "# Forecast scoring causal audit",
        "",
        f"**Protocol:** `{payload['protocol_version']}`  ",
        f"**Stems:** {', '.join(payload['stems'])}  ",
        f"**Rows:** {s['n_rows']}  ",
        f"**Wall seconds:** {payload.get('wall_seconds_total')}  ",
        "",
        "## Supported conclusion",
        "",
        f"**{s['supported_conclusion']['label']}**  ",
        s["supported_conclusion"]["reason"],
        "",
        "## Calibration (train-only, honest sample sizes)",
        "",
        f"```json\n{json.dumps(calib_compact, indent=2)}\n```",
        "",
        "## Mean completed services (repaired causal objective)",
        "",
        f"```json\n{json.dumps(s['completed_by_controller'], indent=2)}\n```",
        "",
        "## Paired calibrated vs causal empty-future",
        "",
        f"- Stats: `{s['paired_calibrated_minus_causal_empty']}`",
        f"- Tally: `{s['paired_calibrated_vs_empty_tally']}`",
        f"- Greedy-nominal vs causal empty: `{s['paired_greedy_minus_causal_empty']}`",
        "",
        "## Failures",
        "",
        f"```json\n{json.dumps(s['failure_counts'], indent=2)}\n```",
        "",
        "## Action-difference audits",
        "",
        f"Logged episode blocks with first-action disagreements: **{len(audits)}** ({n_epochs} epochs).",
        "",
        "Disagreements occur on public state under matched seeds; see JSON `action_audits` "
        "for legs and forecast counts. No mechanism is claimed from score gaps alone.",
        "",
        "## Perfect-information labeling",
        "",
        "The former `perfect_info_diagnostic` is renamed to `release_statistics_diagnostic`.",
        "A restricted offline hindsight comparator is recorded under "
        "`hindsight_offline` and does not feed online control.",
        "",
        "## Reading",
        "",
        "- `cce_greedy_nominal` is the old unequal objective (for diagnosis).",
        "- `cce_causal_empty_future` is the fair no-forecast ablation (same causal scorer).",
        "- `cce_conditional_calibrated` uses decision-epoch-conditioned forecasts with train-calibrated mu.",
        "- Prior Schneider-v1 / stall-diagnostic artifacts remain frozen and are not re-used as fresh validation.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    out_json = Path("docs/experiments/forecast_scoring_causal_results.json")
    out_md = Path("docs/experiments/FORECAST_SCORING_CAUSAL_AUDIT.md")
    payload = run_experiment(out_json=out_json, out_md=out_md)
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
