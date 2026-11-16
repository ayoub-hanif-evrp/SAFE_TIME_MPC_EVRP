"""Corrected development campaign: splits, clustered CIs, economic primary, clean ablations."""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.energy_rebuild import infinite_battery_instance
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
BUDGET = 0.35
N_SCEN = 2
N_REAL = 2
ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_CORRECTED_DEVELOPMENT_RESULTS.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_CORRECTED_DEVELOPMENT_RESULTS.md"
OUT_ABL = ROOT / "docs" / "experiments" / "MPC_CORRECTED_ABLATIONS.md"
OUT_RT = ROOT / "docs" / "experiments" / "MPC_RUNTIME_PROFILE.md"
OUT_TERM = ROOT / "docs" / "experiments" / "MPC_TERMINAL_CORRECTNESS_AUDIT.md"

# Predeclared metrics (Phase 6) — do not redefine retrospectively.
PRIMARY = "economic_objective"
SECONDARY = ("completed_count", "accepted_unfulfilled_count", "rejected_count", "executed_distance")


def _latency(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    ys = sorted(xs)
    n = len(ys)

    def pct(p: float) -> float:
        return ys[min(n - 1, int(p * (n - 1)))]

    return {
        "n": n,
        "mean": sum(ys) / n,
        "median": statistics.median(ys),
        "p50": pct(0.50),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": ys[-1],
        "frac_over_budget": sum(1 for x in ys if x > BUDGET) / n,
    }


def _charge_from_log(log):
    ct = ce = 0.0
    n = 0
    for rec in log:
        if getattr(rec, "kind", None) != "charge_start":
            continue
        data = getattr(rec, "data", {}) or {}
        ct += float(data.get("duration", 0.0) or 0.0)
        soc0 = float(data.get("soc", 0.0) or 0.0)
        tgt = float(data.get("target", soc0) or soc0)
        ce += max(0.0, tgt - soc0)
        n += 1
    return ct, ce, n


def _summarize(case, name, result, ctrl, wall, failure=None):
    if failure:
        return {"controller": name, "failure": failure, "completed_count": None, "wall_seconds": wall}
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    rejected = sum(1 for st in final.values() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
    ct, ce, nc = _charge_from_log(result.log)
    decide = list(getattr(getattr(ctrl, "profile", None), "decide_seconds", []) or [])
    if not decide and getattr(result, "decisions", None):
        decide = [float(getattr(d, "optimize_seconds", 0.0) or 0.0) for d in result.decisions]
    overruns = getattr(getattr(ctrl, "profile", None), "deadline_overruns", None)
    if overruns is None:
        overruns = sum(1 for x in decide if x > BUDGET)
    econ = 100.0 * completed - 250.0 * au - 1.0 * (dist or 0.0)
    return {
        "controller": name,
        "failure": None if rep.ok else f"replay:{rep.code}",
        "replay_ok": rep.ok,
        "completed_count": completed,
        "accepted_unfulfilled_count": au,
        "rejected_count": rejected,
        "executed_distance": dist,
        "charge_time": ct,
        "charge_energy": ce,
        "n_charge_starts": nc,
        "economic_objective": econ,
        "wall_seconds": wall,
        "deadline_overruns": overruns,
        "n_decisions": len(result.decisions),
        "fallback_count": result.fallback_count,
        "decide_latency": _latency(decide),
        "decide_seconds_raw": decide,
        "phase_candidate_gen": list(getattr(getattr(ctrl, "profile", None), "phase_candidate_gen", []) or []),
        "phase_terminal": list(getattr(getattr(ctrl, "profile", None), "phase_terminal", []) or []),
        "phase_scoring": list(getattr(getattr(ctrl, "profile", None), "phase_scoring", []) or []),
        "certificate_status_last": getattr(ctrl, "last_validation_status", None),
        "loss_events": list(getattr(getattr(ctrl, "profile", None), "loss_events", []) or []),
        "terminal_rejects": getattr(getattr(ctrl, "profile", None), "terminal_rejects", None),
    }


def _run(case, ctrl, name):
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
        return _summarize(case, name, result, ctrl, time.perf_counter() - t0)
    except Exception as exc:  # noqa: BLE001
        return _summarize(case, name, None, ctrl, time.perf_counter() - t0, failure=f"{type(exc).__name__}:{exc}")


def _controllers(case, *, arrival, finite, pol, budget):
    inst = case.instance
    h = case.horizon
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=budget,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=100,
    )
    return {
        "b1": FullValidationAlnsMpc(inst, h, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol),
        "m1": CertificateCarryingAlnsMpc(inst, h, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol),
        "cce_greedy_nominal": CertificateCarryingEconomicMpc(
            inst,
            h,
            forecast=arrival,
            n_scenarios=N_SCEN,
            use_forecast=False,
            scoring_mode="greedy_nominal",
            use_persistent_certificate=True,
            **common,
        ),
        "stochastic_cce_causal": CertificateCarryingEconomicMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            scoring_mode="causal",
            use_persistent_certificate=True,
            **common,
        ),
        "commitment_safe_stochastic_mpc": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            forecast_override_margin=50.0,
            **common,
        ),
        "css_mpc_no_forecast": CommitmentSafeStochasticMpc(
            inst, h, use_forecast=False, n_scenarios=1, require_terminal_commitment=True, **common
        ),
        "css_mpc_no_terminal": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=False,
            forecast_override_margin=50.0,
            **common,
        ),
        "css_mpc_no_predictive_charge": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            allow_predictive_charge=False,
            forecast_override_margin=50.0,
            **common,
        ),
        "css_mpc_no_warm_init": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            use_warm_start=False,
            keep_safety_backup_without_warmstart=True,
            forecast_override_margin=50.0,
            **common,
        ),
        "css_mpc_no_warm_no_backup": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            use_warm_start=False,
            keep_safety_backup_without_warmstart=False,
            forecast_override_margin=50.0,
            **common,
        ),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None}
    m = sum(xs) / len(xs)
    if len(xs) == 1:
        return {"n": 1, "mean": m, "std": 0.0, "median": m}
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return {"n": len(xs), "mean": m, "std": var**0.5, "median": statistics.median(xs)}


def _tcrit(df: int) -> float:
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    if df in table:
        return table[df]
    if df > 10:
        return 2.086 if df < 30 else 1.96
    return 12.706


def _paired_clustered(rows, a, b, key=PRIMARY):
    """Average within stem (physical base), then Student-t across stems."""
    by_stem: dict[str, list[float]] = {}
    for row in rows:
        ca, cb = row["controllers"].get(a), row["controllers"].get(b)
        if not ca or not cb or ca.get(key) is None or cb.get(key) is None:
            continue
        if ca.get("replay_ok") is False or cb.get("replay_ok") is False:
            continue
        by_stem.setdefault(row["stem"], []).append(ca[key] - cb[key])
    stem_means = [sum(v) / len(v) for v in by_stem.values() if v]
    tallies = {"better": 0, "worse": 0, "tie": 0}
    for d in stem_means:
        tallies["better" if d > 0 else "worse" if d < 0 else "tie"] += 1
    stats = _mean(stem_means)
    ci = None
    n = stats.get("n") or 0
    if n >= 2 and stats.get("std") is not None:
        se = stats["std"] / math.sqrt(n)
        half = _tcrit(n - 1) * se
        ci = {
            "level": 0.95,
            "method": "stem_clustered_paired_t",
            "df": n - 1,
            "se": se,
            "low": stats["mean"] - half,
            "high": stats["mean"] + half,
        }
    return {
        "metric": key,
        "unit": "stem_mean_of_realization_deltas",
        "n_stems": n,
        "delta": stats,
        "tally_stems": tallies,
        "ci95": ci,
        "per_stem_mean_delta": {s: sum(v) / len(v) for s, v in by_stem.items()},
    }


def development_stems():
    splits = stratified_split_small()
    # Authoritative development only — never label train as development.
    stems = list(splits["development"])
    # Prefer Schneider size mix; keep at most 9 for budget.
    stems = sorted(stems, key=lambda s: (0 if "C5" in s else 1 if "C10" in s else 2, s))[:9]
    labels = {s: "development" for s in stems}
    for s in splits["train"]:
        labels[s] = "train"
    for s in splits["test"]:
        labels[s] = "test"
    return stems, labels, splits


def run_corrected(*, n_real: int = N_REAL, budget: float = BUDGET):
    stems, labels, splits = development_stems()
    assert all(labels[s] == "development" for s in stems)
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)

    rows = []
    for stem in stems:
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, classifications, fleet = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            cell = {
                "stem": stem,
                "split": "development",
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "horizon": case.horizon,
                "controllers": {},
            }
            for name, ctrl in _controllers(case, arrival=arrival, finite=finite, pol=pol, budget=budget).items():
                cell["controllers"][name] = _run(case, ctrl, name)
            rows.append(cell)

    # Small infinite-battery interaction sample (rebuilt arcs).
    inf_rows = []
    for stem in stems[:3]:
        env = environment_seed_for(stem, 0) & 0x7FFFFFFF
        pol = policy_seed_for(stem, 0, "shared")
        episode, _, _ = build_dynamic_episode_v2(
            stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
        )
        case = episode.case
        from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase

        case_inf = BaselineCase(
            case_id=case.case_id + "_infbat",
            instance=infinite_battery_instance(case.instance),
            releases=case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            tags=("infinite_battery",),
        )
        cell = {"stem": stem, "split": "development", "infinite_battery": True, "controllers": {}}
        ctrls = _controllers(case_inf, arrival=arrival, finite=finite, pol=pol, budget=budget)
        for name in ("cce_greedy_nominal", "commitment_safe_stochastic_mpc"):
            cell["controllers"][name] = _run(case_inf, ctrls[name], name)
        inf_rows.append(cell)

    names = list(_controllers(case, arrival=arrival, finite=finite, pol=0, budget=budget))

    def aggregate(rs, names_):
        out = {}
        for name in names_:
            buckets = {
                k: []
                for k in (
                    "economic_objective",
                    "completed_count",
                    "accepted_unfulfilled_count",
                    "rejected_count",
                    "executed_distance",
                    "charge_time",
                )
            }
            raw_lat: list[float] = []
            overruns = 0
            losses = 0
            replay_fail = 0
            for row in rs:
                c = row["controllers"].get(name)
                if not c:
                    continue
                if c.get("replay_ok") is False or c.get("failure"):
                    replay_fail += 1
                    continue
                for k in buckets:
                    buckets[k].append(c.get(k))
                raw_lat.extend(c.get("decide_seconds_raw") or [])
                overruns += int(c.get("deadline_overruns") or 0)
                losses += len(c.get("loss_events") or [])
            out[name] = {
                **{k: _mean(v) for k, v in buckets.items()},
                "decision_latency": _latency(raw_lat),
                "deadline_overruns_sum": overruns,
                "certificate_loss_events_sum": losses,
                "replay_failures": replay_fail,
            }
        return out

    summary = aggregate(rows, names)
    paired = {
        "css_vs_gn_economic_clustered": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "cce_greedy_nominal", PRIMARY
        ),
        "css_vs_gn_completed_clustered": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "cce_greedy_nominal", "completed_count"
        ),
        "css_vs_gn_au_clustered": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "cce_greedy_nominal", "accepted_unfulfilled_count"
        ),
        "css_vs_stochastic_economic": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "stochastic_cce_causal", PRIMARY
        ),
        "css_vs_no_forecast_economic": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "css_mpc_no_forecast", PRIMARY
        ),
        "css_vs_no_terminal_au": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "css_mpc_no_terminal", "accepted_unfulfilled_count"
        ),
        "css_vs_no_predictive_charge_economic": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "css_mpc_no_predictive_charge", PRIMARY
        ),
        "css_vs_no_warm_init_economic": _paired_clustered(
            rows, "commitment_safe_stochastic_mpc", "css_mpc_no_warm_init", PRIMARY
        ),
    }

    econ = paired["css_vs_gn_economic_clustered"]
    gate = {"pass": False, "reason": ""}
    d = econ["delta"].get("mean")
    ci = econ.get("ci95") or {}
    if (
        d is not None
        and ci.get("low") is not None
        and ci["low"] > 0
        and econ["tally_stems"]["better"] > econ["tally_stems"]["worse"]
    ):
        # Also require not catastrophic completed loss
        cdelta = paired["css_vs_gn_completed_clustered"]["delta"].get("mean")
        if cdelta is not None and cdelta >= -0.5:
            gate["pass"] = True
            gate["reason"] = f"Clustered economic CI excludes 0 (mean={d}, ci={ci})."
        else:
            gate["reason"] = f"Economic CI positive but completed stem-mean delta too negative ({cdelta})."
    else:
        gate["reason"] = f"No reliable clustered economic gain vs GN (delta={d}, ci={ci}, tally={econ['tally_stems']})."

    payload = {
        "protocol": "mpc_corrected_development_v1",
        "primary_metric": PRIMARY,
        "secondary_metrics": list(SECONDARY),
        "objective": "100*completed - 250*AU - 1*distance (charging cost via time/opportunity in distance/AU only)",
        "stems": stems,
        "stem_split_labels": {s: labels[s] for s in stems},
        "n_realizations": n_real,
        "budget_seconds": budget,
        "summary": summary,
        "paired_clustered": paired,
        "development_gate": gate,
        "infinite_battery_rows": inf_rows,
        "rows": rows,
        "forecast_override_margin": 50.0,
        "approximation_class": "restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse",
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_md(payload)
    _write_ablations(payload)
    _write_runtime(payload)
    _write_terminal_audit()
    return payload


def _write_md(payload: dict) -> None:
    g = payload["development_gate"]
    OUT_MD.write_text(
        "\n".join(
            [
                "# Corrected MPC development results",
                "",
                f"**Gate:** `{'PASS' if g['pass'] else 'FAIL'}` — {g['reason']}",
                "",
                f"Primary metric: `{payload['primary_metric']}`",
                "",
                f"Stems (all development): {payload['stems']}",
                "",
                "## Summary",
                "",
                "```json",
                json.dumps(payload["summary"], indent=2),
                "```",
                "",
                "## Clustered paired effects",
                "",
                "```json",
                json.dumps(payload["paired_clustered"], indent=2),
                "```",
                "",
                "Reproduce: `python -m safe_time_evrp.mpc_central.mpc_corrected_development_eval`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_ablations(payload: dict) -> None:
    OUT_ABL.write_text(
        "\n".join(
            [
                "# Corrected MPC ablations",
                "",
                "| Ablation | Controllers | Notes |",
                "|---|---|---|",
                "| Forecast | css vs no_forecast | Margin rule on forecast path |",
                "| Terminal | css vs no_terminal | Stage-0 Validate retained |",
                "| Anticipatory charging | css vs no_predictive_charge | Keep incumbent charge only |",
                "| Warm init | css vs no_warm_init | Safety backup retained |",
                "| Warm+backup removed | no_warm_no_backup | Not isolated warm-start |",
                "| Battery | infinite_battery_rows | Rebuilt arcs; small n |",
                "",
                "```json",
                json.dumps(
                    {k: payload["paired_clustered"][k] for k in payload["paired_clustered"] if "css_vs" in k}, indent=2
                ),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_runtime(payload: dict) -> None:
    css = payload["summary"].get("commitment_safe_stochastic_mpc", {})
    gn = payload["summary"].get("cce_greedy_nominal", {})
    OUT_RT.write_text(
        "\n".join(
            [
                "# MPC runtime profile",
                "",
                "Decision-level latency from pooled `decide_seconds_raw` (not episode-mean percentiles).",
                "",
                "## CSS-MPC",
                "",
                "```json",
                json.dumps(css.get("decision_latency"), indent=2),
                "```",
                "",
                f"Deadline overruns (sum): {css.get('deadline_overruns_sum')}",
                "",
                "## Greedy-nominal",
                "",
                "```json",
                json.dumps(gn.get("decision_latency"), indent=2),
                "```",
                "",
                f"Deadline overruns (sum): {gn.get('deadline_overruns_sum')}",
                "",
                "Cooperative 0.35s wall; ALNS not hard-preemptive.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_terminal_audit() -> None:
    OUT_TERM.write_text(
        "\n".join(
            [
                "# MPC terminal correctness audit",
                "",
                "## Problem A — horizon-end freeze",
                "",
                "`freeze_simulator_at_horizon` advances the plant clock to exactly `t+H`.",
                "Partial noninterruptible actions that straddle the boundary keep locks:",
                "",
                "- Travel: proportional SoC drain; remain TRAVELING at origin with reduced residual.",
                "- Charge: proportional SoC accumulation; remain CHARGING.",
                "- Service: remain SERVING; completion only at locked `service_end`.",
                "",
                "## Problem B — residual obligations",
                "",
                "Residuals are taken from the **simulated terminal observation**:",
                "`accepted ∪ in_service − completed` (not `candidate.accepted`).",
                "Includes first-stage accepts, scenario-recourse accepts, and locked in-service.",
                "",
                "## Tests (`tests/test_terminal_horizon_correctness.py`)",
                "",
                "- No event before horizon end",
                "- Partial travel / charging across horizon",
                "- Recourse acceptance reflected in residuals",
                "- Stranded terminal battery",
                "- Terminal service deadline expiration",
                "- Stage-0 Validate OK with terminal infeasible counterexample",
                "",
                "## Approximation class",
                "",
                "Schneider plant has no continuous path geometry. In-transit state is",
                "origin-node + proportional energy. Conservative for SoC and reachability.",
                "Documented; not claimed as exact continuous-space projection.",
                "",
                "## Gate",
                "",
                "Terminal gate marked passed only after the unit tests above succeed.",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    p = run_corrected()
    print(json.dumps({"gate": p["development_gate"], "stems": p["stems"]}, indent=2))
