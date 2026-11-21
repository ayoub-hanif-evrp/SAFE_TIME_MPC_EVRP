"""Publishable multi-dataset MPC evaluation — protocol mpc_paper_multi_dataset_v1.

Plain paper names in outputs; code keys kept for reproducibility.
One method + one nonlinear plant; loaders absorb dataset differences.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import (
    charged_energy_and_time,
    executed_distance_from_log,
)
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.data.evrp_tw_d import extract_root, list_solomon_files, parse_solomon_file
from safe_time_evrp.data.homberger_charging import list_variant_a_instances, parse_homberger_evrptw
from safe_time_evrp.data.paths import evrp_tw_d_dir
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.mpc_nonlinear_ev_ablation import run_ablation as run_nonlinear_ablation
from safe_time_evrp.mpc_central.mpc_spi_development_eval import evaluate_gate
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
BUDGET = 0.35
N_SCEN = 2
N_REAL = 2
PRIMARY = "economic_objective"
PROTOCOL = "mpc_paper_multi_dataset_v1"

# Family-forecast paper campaign tiers (mpc_paper_family_forecast_v1).
SMOKE_BUDGET = 0.5
SMOKE_N_SCEN = 2
SMOKE_ALNS_ITER = 10
SMOKE_ROLLOUT_MAX_EVENTS = 100
PAPER_BUDGET = 2.0
PAPER_N_SCEN = 8
PAPER_ALNS_ITER = 40
PAPER_ROLLOUT_MAX_EVENTS = 250
FAMILY_FORECAST_PROTOCOL = "mpc_paper_family_forecast_v1"
ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_PAPER_EVAL_RESULTS.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_PAPER_EVAL_RESULTS.md"
OUT_HOM_JSON = ROOT / "docs" / "experiments" / "MPC_HOMBERGER_LATENCY.json"
OUT_HOM_MD = ROOT / "docs" / "experiments" / "MPC_HOMBERGER_LATENCY.md"

# Paper display names (no cryptic B1/M1 codes in prose tables).
# Proposed is empty-future commitment-safe RH + SPI (not multi-scenario stochastic).
DISPLAY_NAMES: dict[str, str] = {
    "css_spi": (
        "Proposed: commitment-safe empty-future MPC "
        "(SPI-over-greedy; not multi-scenario demand)"
    ),
    "css_spi_forecast": "Ablation: proposed + multi-scenario demand forecast",
    "css_spi_off": "Ablation: proposed without SPI (legacy ranked selection)",
    "cce_greedy_nominal": "Economic MPC — greedy nominal scoring",
    "full_validation_alns_mpc": "Full-validation ALNS–MPC",
    "certificate_carrying_alns_mpc": "Certificate-carrying ALNS–MPC",
    "stochastic_cce_causal": "Scenario economic MPC (sampled futures)",
}

# Predeclared non-inferiority margin on stem-mean ΔJ (review Observation B).
# One AU costs 250 in J; margin=100 is a conservative "small economic" NI band.
NI_MARGIN_J = 100.0

# Frozen EVRP-TW-D subset (1000 files/scale — wall-time cap, declared before runs).
EVRP_TW_D_FREEZE: dict[str, list[int]] = {
    "Cus_5": [0, 100, 250, 500],
    "Cus_15": [0, 100, 250, 500],
}

# Homberger latency appendix — first two variant-A files.
HOMBERGER_LIMIT = 2


def _latency(xs: list[float], budget: float = BUDGET) -> dict:
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
        "frac_over_budget": sum(1 for x in ys if x > budget) / n,
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


def _summarize(case, name, result, ctrl, wall, failure=None):
    base = {
        "controller": name,
        "display_name": DISPLAY_NAMES.get(name, name),
        "wall_seconds": wall,
    }
    if failure:
        return {**base, "failure": failure, "completed_count": None, "replay_ok": False}
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    rejected = sum(1 for st in final.values() if st == "rejected")
    n_cust = len(case.instance.customer_ids())
    dist = executed_distance_from_log(case.instance, result.log)
    charged_e, charge_t = charged_energy_and_time(result.log)
    n_charge_starts = sum(1 for r in result.log if r.kind == "charge_start")
    makespan = max((float(r.time) for r in result.log), default=0.0)
    decide = list(getattr(getattr(ctrl, "profile", None), "decide_seconds", []) or [])
    if not decide and getattr(result, "decisions", None):
        decide = [float(getattr(d, "optimize_seconds", 0.0) or 0.0) for d in result.decisions]
    overruns = getattr(getattr(ctrl, "profile", None), "deadline_overruns", None)
    if overruns is None:
        overruns = sum(1 for x in decide if x > BUDGET)
    econ = 100.0 * completed - 250.0 * au - 1.0 * (dist or 0.0)
    service_rate = (completed / n_cust) if n_cust else 0.0
    return {
        **base,
        "failure": None if rep.ok else f"replay:{rep.code}",
        "replay_ok": rep.ok,
        "n_customers": n_cust,
        "completed_count": completed,
        "service_rate": service_rate,
        "accepted_unfulfilled_count": au,
        "rejected_count": rejected,
        "executed_distance": dist,
        "executed_charge_time": charge_t,
        "charged_energy": charged_e,
        "n_charge_starts": n_charge_starts,
        "makespan": makespan,
        "economic_objective": econ,
        "optimize_seconds": float(getattr(result, "optimize_seconds", 0.0) or 0.0),
        "simulation_seconds": float(getattr(result, "simulation_seconds", 0.0) or 0.0),
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
        return _summarize(
            case, name, None, ctrl, time.perf_counter() - t0, failure=f"{type(exc).__name__}:{exc}"
        )


def _controllers(case, *, arrival, finite, pol, budget, include_ablations: bool = True):
    """Five baselines/proposed + optional forecast and SPI-off ablations."""
    inst = case.instance
    h = case.horizon
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=budget,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=100,
    )
    ctrls = {
        "full_validation_alns_mpc": FullValidationAlnsMpc(
            inst, h, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol
        ),
        "certificate_carrying_alns_mpc": CertificateCarryingAlnsMpc(
            inst, h, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol
        ),
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
        "css_spi": CommitmentSafeStochasticMpc(
            inst,
            h,
            use_forecast=False,
            n_scenarios=1,
            require_terminal_commitment=True,
            spi_mode=True,
            spi_advantage_margin=0.0,
            hard_terminal_accepts=True,
            accept_slack_gate=True,
            gamma_time=0.0,
            gamma_energy=0.0,
            **common,
        ),
    }
    if include_ablations:
        ctrls["css_spi_forecast"] = CommitmentSafeStochasticMpc(
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
            hard_terminal_accepts=True,
            accept_slack_gate=True,
            gamma_time=0.0,
            gamma_energy=0.0,
            **common,
        )
        ctrls["css_spi_off"] = CommitmentSafeStochasticMpc(
            inst,
            h,
            use_forecast=False,
            n_scenarios=1,
            require_terminal_commitment=True,
            spi_mode=False,
            hard_terminal_accepts=True,
            accept_slack_gate=True,
            gamma_time=0.0,
            gamma_energy=0.0,
            **common,
        )
    return ctrls


def _paired_clustered(rows, a, b, key=PRIMARY, stem_field: str = "stem"):
    by_stem: dict[str, list[float]] = {}
    for row in rows:
        ca, cb = row["controllers"].get(a), row["controllers"].get(b)
        if not ca or not cb or ca.get(key) is None or cb.get(key) is None:
            continue
        if ca.get("replay_ok") is False or ca.get("failure"):
            by_stem.setdefault(row[stem_field], []).append(-1e6 if key == PRIMARY else 1e6)
            continue
        if cb.get("replay_ok") is False or cb.get("failure"):
            by_stem.setdefault(row[stem_field], []).append(1e6 if key == PRIMARY else -1e6)
            continue
        by_stem.setdefault(row[stem_field], []).append(ca[key] - cb[key])
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
        "proposed": a,
        "baseline": b,
        "proposed_display": DISPLAY_NAMES.get(a, a),
        "baseline_display": DISPLAY_NAMES.get(b, b),
        "unit": "stem_mean_of_realization_deltas",
        "n_stems": n,
        "delta": stats,
        "tally_stems": tallies,
        "ci95": ci,
        "per_stem_mean_delta": {s: sum(v) / len(v) for s, v in by_stem.items()},
    }


def _aggregate(rows, names):
    out = {}
    for name in names:
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
        overruns = losses = replay_fail = 0
        spi_k = spi_o = 0
        for row in rows:
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
            "display_name": DISPLAY_NAMES.get(name, name),
            **{k: _mean(v) for k, v in buckets.items()},
            "decision_latency": _latency(raw_lat),
            "deadline_overruns_sum": overruns,
            "certificate_loss_events_sum": losses,
            "replay_failures": replay_fail,
            "spi_keeps_sum": spi_k,
            "spi_overrides_sum": spi_o,
        }
    return out


def _schneider_development_stems():
    splits = stratified_split_small()
    stems = sorted(
        splits["development"],
        key=lambda s: (0 if "C5" in s else 1 if "C10" in s else 2, s),
    )
    return stems, splits


def run_schneider_campaign(*, n_real: int = N_REAL, budget: float = BUDGET) -> dict:
    stems, splits = _schneider_development_stems()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    rows = []
    for stem in stems:
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, _, _ = build_dynamic_episode_v2(
                stem,
                environment_seed=env,
                policy_seed=pol,
                dynamicity="medium",
                split="development",
            )
            case = episode.case
            cell = {
                "dataset": "schneider_evrptw",
                "stem": stem,
                "split": "development",
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "horizon": case.horizon,
                "controllers": {},
            }
            for name, ctrl in _controllers(
                case, arrival=arrival, finite=finite, pol=pol, budget=budget, include_ablations=True
            ).items():
                cell["controllers"][name] = _run(case, ctrl, name)
            rows.append(cell)

    names = list(
        _controllers(case, arrival=arrival, finite=finite, pol=0, budget=budget, include_ablations=True)
    )
    summary = _aggregate(rows, names)
    paired = {
        "proposed_vs_greedy_nominal_j": _paired_clustered(rows, "css_spi", "cce_greedy_nominal", PRIMARY),
        "proposed_vs_greedy_nominal_au": _paired_clustered(
            rows, "css_spi", "cce_greedy_nominal", "accepted_unfulfilled_count"
        ),
        "proposed_vs_full_validation_alns_j": _paired_clustered(
            rows, "css_spi", "full_validation_alns_mpc", PRIMARY
        ),
        "proposed_vs_certificate_carrying_alns_j": _paired_clustered(
            rows, "css_spi", "certificate_carrying_alns_mpc", PRIMARY
        ),
        "proposed_vs_scenario_economic_mpc_j": _paired_clustered(
            rows, "css_spi", "stochastic_cce_causal", PRIMARY
        ),
        "proposed_vs_forecast_ablation_j": _paired_clustered(rows, "css_spi", "css_spi_forecast", PRIMARY),
        "proposed_vs_spi_off_ablation_j": _paired_clustered(rows, "css_spi", "css_spi_off", PRIMARY),
    }
    # Development gate (tally / mean) — internal criterion, not formal NI.
    gate = evaluate_gate(
        {
            "css_spi_vs_gn_economic": paired["proposed_vs_greedy_nominal_j"],
            "css_spi_vs_gn_au": paired["proposed_vs_greedy_nominal_au"],
        },
        protocol=PROTOCOL,
    )
    lat = summary.get("css_spi", {}).get("decision_latency") or {}
    gate["compute_p50"] = lat.get("p50")
    gate["compute_p99"] = lat.get("p99")
    gate["compute_ok"] = (lat.get("p50") is not None) and (lat["p50"] <= budget * 1.5)
    if gate["pass"] and not gate["compute_ok"]:
        gate["pass"] = False
        gate["reason"] += f" Compute FAIL p50={lat.get('p50')}"

    # Formal-style NI check: CI low ≥ −NI_MARGIN (prespecified margin).
    econ = paired["proposed_vs_greedy_nominal_j"]
    ci = econ.get("ci95") or {}
    formal_ni = {
        "margin": NI_MARGIN_J,
        "prespecified": True,
        "ci_low": ci.get("low"),
        "pass": ci.get("low") is not None and ci["low"] >= -NI_MARGIN_J,
        "note": (
            "Formal NI requires CI_low ≥ −Δ with Δ justified a priori. "
            "Development gate PASS ≠ formal NI if CI includes large negatives."
        ),
    }

    # Certificate-loss concentration (review Observation D).
    loss_by_cell = []
    for row in rows:
        c = row["controllers"].get("css_spi") or {}
        n_loss = len(c.get("loss_events") or [])
        if n_loss:
            loss_by_cell.append(
                {
                    "stem": row["stem"],
                    "realization_index": row["realization_index"],
                    "n_loss_events": n_loss,
                }
            )

    return {
        "role": "primary_economic",
        "dataset": "schneider_evrptw",
        "scientific_identity": (
            "empty-future commitment-safe receding-horizon MPC with SPI-over-greedy; "
            "multi-scenario demand is an ablation, not the proposed claim"
        ),
        "stems": stems,
        "n_realizations": n_real,
        "budget_seconds": budget,
        "display_names": DISPLAY_NAMES,
        "summary": summary,
        "paired_clustered": paired,
        "development_gate": gate,
        "formal_noninferiority": formal_ni,
        "certificate_loss_cells": loss_by_cell,
        "spi_keeps_sum": summary.get("css_spi", {}).get("spi_keeps_sum"),
        "spi_overrides_sum": summary.get("css_spi", {}).get("spi_overrides_sum"),
        "rows": rows,
        "test_split_sealed": True,
    }


def _evrp_dynamic_case(path: Path, *, scale: str, pol: int) -> BaselineCase:
    inst = parse_solomon_file(path)
    cust = inst.customer_ids()
    n_known = max(1, int(0.3 * len(cust)))
    releases = []
    for i, cid in enumerate(cust):
        t = 0.0 if i < n_known else 5.0 * (i - n_known + 1)
        releases.append((cid, t))
    depot_due = float(inst.node(inst.depot_id).window.due)
    fleet = 1 if scale == "Cus_5" else 2
    return BaselineCase(
        case_id=f"evrp_tw_d|{scale}|{path.stem}",
        instance=inst,
        releases=releases,
        fleet_size=fleet,
        horizon=depot_due,
        max_replan_interval=max(5.0, depot_due / 40.0),
        t_max=depot_due,
        tags=("evrp_tw_d", scale, "confirmatory"),
    )


def run_evrp_tw_d_campaign(*, budget: float = BUDGET) -> dict:
    root = extract_root(evrp_tw_d_dir())
    # Forecast priors from Schneider train (shared plant family; EVRP has no train split here).
    splits = stratified_split_small()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)

    frozen_paths: list[tuple[str, Path]] = []
    for scale, idxs in EVRP_TW_D_FREEZE.items():
        files = list_solomon_files(root, scale=scale)
        for i in idxs:
            if i < len(files):
                frozen_paths.append((scale, files[i]))

    rows = []
    for scale, path in frozen_paths:
        case = _evrp_dynamic_case(path, scale=scale, pol=11)
        cell = {
            "dataset": "evrp_tw_d",
            "stem": f"{scale}/{path.stem}",
            "scale": scale,
            "split": "confirmatory_freeze",
            "realization_index": 0,
            "horizon": case.horizon,
            "controllers": {},
        }
        for name, ctrl in _controllers(
            case, arrival=arrival, finite=finite, pol=11, budget=budget, include_ablations=False
        ).items():
            cell["controllers"][name] = _run(case, ctrl, name)
        rows.append(cell)

    names = list(
        _controllers(
            case, arrival=arrival, finite=finite, pol=0, budget=budget, include_ablations=False
        )
    )
    summary = _aggregate(rows, names)
    paired = {
        "proposed_vs_greedy_nominal_j": _paired_clustered(rows, "css_spi", "cce_greedy_nominal", PRIMARY),
        "proposed_vs_greedy_nominal_au": _paired_clustered(
            rows, "css_spi", "cce_greedy_nominal", "accepted_unfulfilled_count"
        ),
        "proposed_vs_full_validation_alns_j": _paired_clustered(
            rows, "css_spi", "full_validation_alns_mpc", PRIMARY
        ),
        "proposed_vs_certificate_carrying_alns_j": _paired_clustered(
            rows, "css_spi", "certificate_carrying_alns_mpc", PRIMARY
        ),
        "proposed_vs_scenario_economic_mpc_j": _paired_clustered(
            rows, "css_spi", "stochastic_cce_causal", PRIMARY
        ),
    }
    return {
        "role": "secondary_geography_confirmatory",
        "dataset": "evrp_tw_d",
        "freeze_rule": "indices_per_scale",
        "freeze_indices": EVRP_TW_D_FREEZE,
        "frozen_stems": [r["stem"] for r in rows],
        "n_cells": len(rows),
        "budget_seconds": budget,
        "display_names": {k: DISPLAY_NAMES[k] for k in names},
        "summary": summary,
        "paired_clustered": paired,
        "rows": rows,
        "note": (
            "Full Cus_5/Cus_15 archives have 1000 files each; this freeze is predeclared "
            "for wall-time. Not pooled with Schneider for average J."
        ),
    }


def run_homberger_latency(*, budget: float = BUDGET, n_decides: int = 5) -> dict:
    """Latency appendix: timed ``decide()`` calls on large Homberger instances.

    Full closed-loop episodes on 1000-customer graphs stall under the cooperative
    budget; the paper claim here is decision latency, not economic ranking.
    """
    from safe_time_evrp.models.state import Anchor, Observation, VehicleView
    from safe_time_evrp.testbed.constructor import make_observation

    files = list_variant_a_instances(limit=HOMBERGER_LIMIT)
    rows = []
    for path in files:
        inst = parse_homberger_evrptw(path)
        cust = inst.customer_ids()[:25]
        depot_due = float(inst.node(inst.depot_id).window.due)
        horizon = min(depot_due, 400.0)
        # Warm fleet observation with a modest announcement set.
        obs0 = make_observation(inst, fleet_size=4, start_time=0.0)
        # Replace released_open with capped customers.
        vehicles = []
        for v in obs0.vehicles:
            vehicles.append(
                VehicleView(
                    v.id,
                    v.status,
                    v.node,
                    v.soc,
                    v.load,
                    v.onboard,
                    Anchor(v.anchor.node, v.anchor.time, v.anchor.soc, v.anchor.load, v.anchor.onboard),
                    v.locked_destination,
                )
            )
        obs = Observation(
            0.0,
            tuple(vehicles),
            tuple(cust),
            (),
            (),
            (),
            (),
            (),
            public_customer_count=len(inst.customer_ids()),
        )
        common = dict(
            alns_iterations=6,
            time_limit_seconds=budget,
            seed=5,
            max_replan_interval=25.0,
            rollout_max_events=60,
        )
        ctrls = {
            "css_spi": CommitmentSafeStochasticMpc(
                inst,
                horizon,
                use_forecast=False,
                n_scenarios=1,
                require_terminal_commitment=True,
                spi_mode=True,
                spi_advantage_margin=0.0,
                hard_terminal_accepts=True,
                accept_slack_gate=True,
                gamma_time=0.0,
                gamma_energy=0.0,
                **common,
            ),
            "cce_greedy_nominal": CertificateCarryingEconomicMpc(
                inst,
                horizon,
                forecast=None,
                n_scenarios=1,
                use_forecast=False,
                scoring_mode="greedy_nominal",
                use_persistent_certificate=True,
                **common,
            ),
        }
        cell = {
            "dataset": "evrptw_homberger_charging",
            "stem": path.stem,
            "n_customers_announced": len(cust),
            "n_customers_instance": len(inst.customer_ids()),
            "bench": "timed_decide_only",
            "controllers": {},
        }
        for name, ctrl in ctrls.items():
            times: list[float] = []
            failure = None
            t_wall0 = time.perf_counter()
            try:
                for i in range(n_decides):
                    d = ctrl.decide(obs, "request_release" if i == 0 else "replan_interval")
                    times.append(float(d.optimize_seconds or 0.0))
            except Exception as exc:  # noqa: BLE001
                failure = f"{type(exc).__name__}:{exc}"
            wall = time.perf_counter() - t_wall0
            cell["controllers"][name] = {
                "controller": name,
                "display_name": DISPLAY_NAMES.get(name, name),
                "failure": failure,
                "replay_ok": failure is None,
                "n_decisions": len(times),
                "decide_seconds_raw": times,
                "decide_latency": _latency(times),
                "wall_seconds": wall,
                "economic_objective": None,
                "completed_count": None,
                "accepted_unfulfilled_count": None,
                "executed_distance": None,
                "deadline_overruns": sum(1 for x in times if x > budget),
                "loss_events": list(getattr(getattr(ctrl, "profile", None), "loss_events", []) or []),
                "spi_keeps": int(getattr(getattr(ctrl, "profile", None), "spi_keeps", 0) or 0),
                "spi_overrides": int(getattr(getattr(ctrl, "profile", None), "spi_overrides", 0) or 0),
            }
        rows.append(cell)

    # Latency-focused aggregate (do not drop failed economic fields).
    summary = {}
    for name in ("css_spi", "cce_greedy_nominal"):
        raw: list[float] = []
        overruns = 0
        fails = 0
        for row in rows:
            c = row["controllers"][name]
            if c.get("failure"):
                fails += 1
            raw.extend(c.get("decide_seconds_raw") or [])
            overruns += int(c.get("deadline_overruns") or 0)
        summary[name] = {
            "display_name": DISPLAY_NAMES[name],
            "decision_latency": _latency(raw, budget=budget),
            "deadline_overruns_sum": overruns,
            "decide_failures": fails,
            "n_cells": len(rows),
        }

    payload = {
        "protocol": PROTOCOL,
        "role": "scalability_latency_appendix",
        "dataset": "evrptw_homberger_charging",
        "frozen_files": [p.name for p in files],
        "customer_announce_cap": 25,
        "n_decides_per_controller": n_decides,
        "budget_seconds": budget,
        "display_names": {
            "css_spi": DISPLAY_NAMES["css_spi"],
            "cce_greedy_nominal": DISPLAY_NAMES["cce_greedy_nominal"],
        },
        "summary": summary,
        "rows": rows,
        "claim_scope": (
            "Decision latency only (timed decide on large instances). "
            "Not a main economic ranking claim."
        ),
    }
    OUT_HOM_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_HOM_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Homberger latency appendix",
        "",
        f"- Protocol: `{PROTOCOL}`",
        f"- Files: {', '.join(payload['frozen_files'])}",
        f"- Announced customers/cap: {payload['customer_announce_cap']}",
        f"- Decides per controller: {n_decides}",
        "",
        "## Decision latency",
        "",
    ]
    for key in ("css_spi", "cce_greedy_nominal"):
        lat = summary[key].get("decision_latency") or {}
        lines.append(
            f"- **{DISPLAY_NAMES[key]}**: p50={lat.get('p50')}, p99={lat.get('p99')}, "
            f"n={lat.get('n')}, fails={summary[key].get('decide_failures')}"
        )
    lines.extend(["", payload["claim_scope"], ""])
    OUT_HOM_MD.write_text("\n".join(lines), encoding="utf-8")
    return payload


def _fmt_paired(p: dict) -> str:
    ci = p.get("ci95") or {}
    return (
        f"{p.get('proposed_display', p.get('proposed'))} − "
        f"{p.get('baseline_display', p.get('baseline'))}: "
        f"mean={p['delta'].get('mean')}, CI=[{ci.get('low')}, {ci.get('high')}], "
        f"tally={p['tally_stems']}"
    )


def _write_paper_md(payload: dict) -> None:
    sch = payload["schneider"]
    evrp = payload["evrp_tw_d"]
    g = sch["development_gate"]
    lines = [
        "# MPC paper evaluation (multi-dataset)",
        "",
        f"**Protocol:** `{PROTOCOL}`",
        "",
        "## Controller names (paper)",
        "",
    ]
    for k, v in DISPLAY_NAMES.items():
        lines.append(f"- `{k}` → **{v}**")
    lines.extend(
        [
            "",
            "## Dataset roles",
            "",
            "- **Schneider E-VRPTW** — primary economic table (development; test sealed)",
            "- **EVRP-TW-D** — confirmatory geography (frozen Cus_5 / Cus_15 subset)",
            "- **Homberger + chargers** — latency appendix only (separate file)",
            "",
            f"## Schneider development gate: {'PASS' if g.get('pass') else 'FAIL'}",
            "",
            f"{g.get('reason')}",
            "",
            f"- Compute p50={g.get('compute_p50')}, p99={g.get('compute_p99')}",
            (
                f"- Formal NI (prespecified Δ={sch.get('formal_noninferiority', {}).get('margin')}): "
                f"{'PASS' if sch.get('formal_noninferiority', {}).get('pass') else 'FAIL'} "
                f"(CI low={sch.get('formal_noninferiority', {}).get('ci_low')})"
            ),
            (
                f"- SPI keeps/overrides (Schneider): "
                f"{sch.get('spi_keeps_sum')}/{sch.get('spi_overrides_sum')}"
            ),
            f"- Certificate-loss cells: {len(sch.get('certificate_loss_cells') or [])}",
            f"- Identity: {sch.get('scientific_identity')}",
            "",
            "### Paired deltas (proposed − baseline)",
            "",
        ]
    )
    for key in (
        "proposed_vs_greedy_nominal_j",
        "proposed_vs_greedy_nominal_au",
        "proposed_vs_full_validation_alns_j",
        "proposed_vs_certificate_carrying_alns_j",
        "proposed_vs_scenario_economic_mpc_j",
        "proposed_vs_forecast_ablation_j",
        "proposed_vs_spi_off_ablation_j",
    ):
        lines.append(f"- {_fmt_paired(sch['paired_clustered'][key])}")
    lines.extend(
        [
            "",
            "## EVRP-TW-D confirmatory",
            "",
            f"- Frozen stems: {', '.join(evrp['frozen_stems'])}",
            f"- Note: {evrp['note']}",
            "",
        ]
    )
    for key in (
        "proposed_vs_greedy_nominal_j",
        "proposed_vs_full_validation_alns_j",
        "proposed_vs_certificate_carrying_alns_j",
        "proposed_vs_scenario_economic_mpc_j",
    ):
        lines.append(f"- {_fmt_paired(evrp['paired_clustered'][key])}")
    lines.extend(
        [
            "",
            "## Nonlinear charging ablation",
            "",
            f"- See `MPC_NONLINEAR_EV_ABLATION.md` (mechanism_holds="
            f"{payload.get('nonlinear_ev', {}).get('mechanism_demo', {}).get('mechanism_holds')})",
            "",
            "## Homberger latency",
            "",
            "- See `MPC_HOMBERGER_LATENCY.md`",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_all() -> dict:
    print("=== Schneider primary ===", flush=True)
    schneider = run_schneider_campaign()
    print("=== EVRP-TW-D confirmatory ===", flush=True)
    evrp = run_evrp_tw_d_campaign()
    print("=== Homberger latency ===", flush=True)
    homberger = run_homberger_latency()
    print("=== Nonlinear EV ablation refresh ===", flush=True)
    nonlinear = run_nonlinear_ablation()
    payload = {
        "protocol": PROTOCOL,
        "objective": "100*completed - 250*AU - 1*distance",
        "display_names": DISPLAY_NAMES,
        "architecture": {
            "method": "commitment_safe_stochastic_mpc_spi",
            "plant": "nonlinear_piecewise_charge",
            "adapters_absorb_dataset_differences": True,
        },
        "schneider": schneider,
        "evrp_tw_d": evrp,
        "homberger_latency_ref": str(OUT_HOM_JSON.relative_to(ROOT)).replace("\\", "/"),
        "nonlinear_ev": {
            "mechanism_demo": nonlinear.get("mechanism_demo"),
            "physical_charge_gap_near_full": nonlinear.get("physical_charge_gap_near_full"),
            "paired_nonlinear_minus_linear": nonlinear.get("paired_nonlinear_minus_linear"),
        },
        "homberger": {
            "summary": homberger.get("summary"),
            "frozen_files": homberger.get("frozen_files"),
            "claim_scope": homberger.get("claim_scope"),
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_paper_md(payload)
    return payload


if __name__ == "__main__":
    out = run_all()
    print(
        json.dumps(
            {
                "protocol": out["protocol"],
                "schneider_gate": out["schneider"]["development_gate"],
                "evrp_n": out["evrp_tw_d"]["n_cells"],
                "homberger_files": out["homberger"]["frozen_files"],
                "mechanism_holds": out["nonlinear_ev"]["mechanism_demo"].get("mechanism_holds"),
            },
            indent=2,
        )
    )
