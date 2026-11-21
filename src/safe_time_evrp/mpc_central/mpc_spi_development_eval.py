"""Predeclared SPI development campaign — one freeze, one gate, stop if fail.

Controllers: CSS-SPI (proposed), CSS-empty, greedy-nominal, M1, B1, stochastic CCE.
Primary J = 100*completed - 250*AU - D. Stem-clustered 95% CI gate.
"""

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
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
BUDGET = 0.35
N_SCEN = 2
N_REAL = 2
PRIMARY = "economic_objective"
ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_SPI_DEVELOPMENT_RESULTS.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_SPI_DEVELOPMENT_RESULTS.md"


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
        "p99": pct(0.99),
        "max": ys[-1],
        "frac_over_budget": sum(1 for x in ys if x > BUDGET) / n,
    }


def _summarize(case, name, result, ctrl, wall, failure=None):
    if failure:
        return {"controller": name, "failure": failure, "completed_count": None, "wall_seconds": wall}
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    rejected = sum(1 for st in final.values() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
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
        "economic_objective": econ,
        "wall_seconds": wall,
        "deadline_overruns": overruns,
        "n_decisions": len(result.decisions),
        "fallback_count": result.fallback_count,
        "decide_latency": _latency(decide),
        "decide_seconds_raw": decide,
        "spi_keeps": int(getattr(getattr(ctrl, "profile", None), "spi_keeps", 0) or 0),
        "spi_overrides": int(getattr(getattr(ctrl, "profile", None), "spi_overrides", 0) or 0),
        "loss_events": list(getattr(getattr(ctrl, "profile", None), "loss_events", []) or []),
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
        # Proposed after forecast demotion (SPI+forecast lost to SPI+empty on v1).
        "css_spi": CommitmentSafeStochasticMpc(
            inst,
            h,
            use_forecast=False,
            n_scenarios=1,
            require_terminal_commitment=True,
            spi_mode=True,
            spi_advantage_margin=0.0,
            **common,
        ),
        # Ablation: forecast path (must beat proposed to reclaim prediction claim).
        "css_spi_forecast": CommitmentSafeStochasticMpc(
            inst,
            h,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            spi_mode=True,
            spi_advantage_margin=0.0,
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
    by_stem: dict[str, list[float]] = {}
    for row in rows:
        ca, cb = row["controllers"].get(a), row["controllers"].get(b)
        if not ca or not cb or ca.get(key) is None or cb.get(key) is None:
            continue
        # Include all failures: treat missing/failed replay as large negative delta for a.
        if ca.get("replay_ok") is False or ca.get("failure"):
            by_stem.setdefault(row["stem"], []).append(-1e6 if key == PRIMARY else 1e6)
            continue
        if cb.get("replay_ok") is False or cb.get("failure"):
            by_stem.setdefault(row["stem"], []).append(1e6 if key == PRIMARY else -1e6)
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
    stems = sorted(splits["development"], key=lambda s: (0 if "C5" in s else 1 if "C10" in s else 2, s))[:9]
    return stems, splits


def evaluate_gate(paired: dict, *, protocol: str = "mpc_paper_gate_v1") -> dict:
    """Paper Gate A: non-inferior SPI-MPC vs greedy-nominal (stem-clustered).

    Pass if any of:
      (1) CI low for ΔJ = J(CSS)−J(GN) ≥ 0
      (2) mean ΔJ ≥ 0 and AU CI high < 0 (AU reduction)
      (3) mean ΔJ ≥ 0, tally better ≥ worse, and no systematic AU increase
    """
    econ = paired["css_spi_vs_gn_economic"]
    au = paired["css_spi_vs_gn_au"]
    d = econ["delta"].get("mean")
    ci = econ.get("ci95") or {}
    au_d = au["delta"].get("mean")
    au_ci = au.get("ci95") or {}
    tally = econ["tally_stems"]
    # AU reduction ⇒ negative delta for CSS−GN.
    au_sig = au_d is not None and au_ci.get("high") is not None and au_ci["high"] < 0
    # No systematic AU increase: mean AU delta ≤ 0, or AU CI low not clearly > 0.
    au_no_increase = au_d is not None and (
        au_d <= 1e-9 or (au_ci.get("low") is not None and au_ci["low"] <= 1e-9)
    )
    j_noninf_ci = d is not None and ci.get("low") is not None and ci["low"] >= -1e-9
    j_mean_nonneg = d is not None and d >= -1e-9
    if j_noninf_ci:
        return {
            "pass": True,
            "protocol": protocol,
            "reason": f"Non-inferior J: CI low ≥ 0 (mean={d}, ci={ci}).",
        }
    if j_mean_nonneg and au_sig:
        return {
            "pass": True,
            "protocol": protocol,
            "reason": (
                f"Mean ΔJ ≥ 0 (mean={d}, ci={ci}) + significant AU reduction "
                f"(mean={au_d}, ci={au_ci})."
            ),
        }
    if j_mean_nonneg and tally["better"] >= tally["worse"] and au_no_increase:
        return {
            "pass": True,
            "protocol": protocol,
            "reason": (
                f"Mean ΔJ ≥ 0 with tally better≥worse and no AU increase "
                f"(mean={d}, tally={tally}, AU mean={au_d}, AU ci={au_ci})."
            ),
        }
    return {
        "pass": False,
        "protocol": protocol,
        "reason": (
            f"Gate FAIL: non-inferiority vs GN not established. "
            f"J delta={d}, ci={ci}, tally={tally}; AU delta={au_d}, ci={au_ci}."
        ),
    }


def run_spi_campaign(
    *,
    n_real: int = N_REAL,
    budget: float = BUDGET,
    protocol: str = "mpc_paper_gate_v1",
) -> dict:
    stems, splits = development_stems()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)

    rows = []
    for stem in stems:
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, _, _ = build_dynamic_episode_v2(
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

    names = list(_controllers(case, arrival=arrival, finite=finite, pol=0, budget=budget))

    def aggregate(rs, names_):
        out = {}
        for name in names_:
            buckets = {
                k: []
                for k in (
                    PRIMARY,
                    "completed_count",
                    "accepted_unfulfilled_count",
                    "rejected_count",
                    "executed_distance",
                )
            }
            raw_lat: list[float] = []
            overruns = 0
            losses = 0
            replay_fail = 0
            spi_k = spi_o = 0
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
                spi_k += int(c.get("spi_keeps") or 0)
                spi_o += int(c.get("spi_overrides") or 0)
            out[name] = {
                **{k: _mean(v) for k, v in buckets.items()},
                "decision_latency": _latency(raw_lat),
                "deadline_overruns_sum": overruns,
                "certificate_loss_events_sum": losses,
                "replay_failures": replay_fail,
                "spi_keeps_sum": spi_k,
                "spi_overrides_sum": spi_o,
            }
        return out

    summary = aggregate(rows, names)
    paired = {
        "css_spi_vs_gn_economic": _paired_clustered(rows, "css_spi", "cce_greedy_nominal", PRIMARY),
        "css_spi_vs_gn_au": _paired_clustered(rows, "css_spi", "cce_greedy_nominal", "accepted_unfulfilled_count"),
        "css_spi_vs_gn_completed": _paired_clustered(rows, "css_spi", "cce_greedy_nominal", "completed_count"),
        "css_spi_vs_forecast_economic": _paired_clustered(rows, "css_spi", "css_spi_forecast", PRIMARY),
        "css_spi_vs_stochastic_cce_economic": _paired_clustered(rows, "css_spi", "stochastic_cce_causal", PRIMARY),
        "css_spi_vs_m1_economic": _paired_clustered(rows, "css_spi", "m1", PRIMARY),
        "css_spi_vs_b1_economic": _paired_clustered(rows, "css_spi", "b1", PRIMARY),
    }
    gate = evaluate_gate(paired, protocol=protocol)
    lat = summary.get("css_spi", {}).get("decision_latency") or {}
    compute_ok = (lat.get("p50") is not None) and (lat["p50"] <= budget * 1.5)
    gate["compute_p50"] = lat.get("p50")
    gate["compute_p99"] = lat.get("p99")
    gate["compute_ok"] = compute_ok
    if gate["pass"] and not compute_ok:
        gate["pass"] = False
        gate["reason"] += f" Compute gate FAIL: css_spi p50={lat.get('p50')} > 1.5*budget={budget * 1.5}."

    payload = {
        "protocol": protocol,
        "selection_law": "spi_crn_stage0_matched_gn_base",
        "spi_advantage_margin": 0.0,
        "forecast_demoted": True,
        "primary_metric": PRIMARY,
        "objective": "100*completed - 250*AU - 1*distance",
        "stems": stems,
        "n_realizations": n_real,
        "budget_seconds": budget,
        "summary": summary,
        "paired_clustered": paired,
        "development_gate": gate,
        "rows": rows,
        "approximation_class": "commitment_safe_stochastic_mpc_spi_over_gn",
        "stop_rule": (
            "If development_gate.pass is false after stage-0-matched SPI base: stop inventing "
            "controller variants; reframe as mechanism-only with explicit non-superiority vs GN."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_md(payload)
    return payload


def _write_md(payload: dict) -> None:
    g = payload["development_gate"]
    lines = [
        "# MPC SPI development campaign",
        "",
        f"**Gate: {'PASS' if g.get('pass') else 'FAIL'}** — {g.get('reason')}",
        "",
        f"- Protocol: `{payload['protocol']}`",
        f"- Selection law: `{payload['selection_law']}` (δ_SPI={payload['spi_advantage_margin']})",
        f"- Stems (development only): {', '.join(payload['stems'])}",
        f"- Realizations / stem: {payload['n_realizations']}",
        f"- Cooperative budget: {payload['budget_seconds']}s",
        "",
        "## Stem-clustered paired deltas (CSS-SPI − baseline)",
        "",
    ]
    for key, label in (
        ("css_spi_vs_gn_economic", "vs greedy-nominal J"),
        ("css_spi_vs_gn_au", "vs greedy-nominal AU"),
        ("css_spi_vs_forecast_economic", "vs CSS-SPI+forecast J (proposed is empty)"),
        ("css_spi_vs_stochastic_cce_economic", "vs stochastic CCE J"),
    ):
        p = payload["paired_clustered"][key]
        ci = p.get("ci95") or {}
        lines.append(
            f"- **{label}**: mean={p['delta'].get('mean')}, "
            f"CI=[{ci.get('low')}, {ci.get('high')}], tally={p['tally_stems']}"
        )
    lines.extend(["", "## Summary means", "", "```json", json.dumps(payload["summary"], indent=2)[:8000], "```", ""])
    if not g.get("pass"):
        lines.extend(
            [
                "## Stop rule",
                "",
                "Development gate failed. Per recovery plan: **stop** — do not invent another controller variant.",
                "Reframe contribution (mechanism / certificate / scenario-terminal honesty) or lower venue ambition.",
                "",
            ]
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    p = run_spi_campaign()
    print(json.dumps({"gate": p["development_gate"], "n_rows": len(p["rows"])}, indent=2))
