"""Full Schneider EVRPTW campaign: all instances, rich ops + economic metrics.

Protocol: ``mpc_schneider_full_v1``
Proposed stack: recovery forecast + M1–M4 (not MSA defaults).

Speed: parallel ProcessPool over independent cells (same math as serial).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

from safe_time_evrp.data.dynamic_schneider import list_schneider_refs
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.mpc_central.family_forecast_controllers import make_proposed_mpc
from safe_time_evrp.mpc_central.family_forecasts import load_family_forecasts
from safe_time_evrp.mpc_central.mpc_paper_eval import (
    ALNS_ITER,
    BUDGET,
    PRIMARY,
    _controllers,
    _paired_clustered,
    _run,
)
from safe_time_evrp.mpc_central.mpc_spi_development_eval import evaluate_gate

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "docs" / "experiments" / "MPC_RECOVERY_SPLITS.json"
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_SCHNEIDER_FULL_RESULTS.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_SCHNEIDER_FULL_RESULTS.md"
PROTOCOL = "mpc_schneider_full_v1"
NI_MARGIN = 100.0

# All instances: 2 reals on small; 1 real on 100-customer (still every stem once+).
N_REAL_SMALL = 2
N_REAL_100 = 1
DEFAULT_WORKERS = 8

METRIC_KEYS = [
    "economic_objective",
    "completed_count",
    "service_rate",
    "accepted_unfulfilled_count",
    "rejected_count",
    "executed_distance",
    "executed_charge_time",
    "charged_energy",
    "n_charge_starts",
    "makespan",
    "wall_seconds",
    "optimize_seconds",
]


def _type12(stem: str) -> str:
    m = re.match(r"^(?:rc|c|r)(\d)", stem.lower())
    return "type1" if m and m.group(1) == "1" else "type2"


def _formal_ni(paired: dict, margin: float = NI_MARGIN) -> dict:
    ci = paired.get("ci95") or {}
    low = ci.get("low")
    return {
        "margin": margin,
        "pass": low is not None and low >= -margin,
        "ci_low": low,
        "mean": (paired.get("delta") or {}).get("mean"),
    }


def _means(rows: list[dict], ctrl: str) -> dict:
    out = {}
    for k in METRIC_KEYS:
        xs = []
        for r in rows:
            c = r["controllers"].get(ctrl) or {}
            if c.get("failure") or c.get(k) is None:
                continue
            xs.append(float(c[k]))
        out[k] = {"n": len(xs), "mean": (mean(xs) if xs else None)}
    return out


def _method_cfg() -> dict:
    cfg = dict(json.loads(REC.read_text(encoding="utf-8"))["method_stack_defaults"])
    cfg["selection_mode"] = "mean_score"
    cfg["scenario_sample_mode"] = "stratified"
    cfg["adaptive_compute"] = True
    cfg["use_forecast"] = True
    cfg["n_scenarios"] = int(cfg.get("n_scenarios", 2))
    return cfg


def _eval_cell(job: dict) -> dict:
    """Worker: one (stem, realization) cell. Identity identical to serial path."""
    # Avoid BLAS/OpenMP oversubscription when many workers share a CPU.
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    stem = job["stem"]
    ridx = int(job["realization_index"])
    size = int(job["size_bucket"])
    cfg = job["cfg"]
    t_cell = time.perf_counter()

    pack = load_family_forecasts("schneider")
    split = "development" if _type12(stem) == "type1" else "test"
    env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
    pol = policy_seed_for(stem, ridx, "shared")
    episode, _, _ = build_dynamic_episode_v2(
        stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split=split
    )
    case = episode.case
    cell = {
        "dataset": "schneider_evrptw",
        "stem": stem,
        "size_bucket": size,
        "family": "rc" if stem.lower().startswith("rc") else ("r" if stem.lower().startswith("r") else "c"),
        "type12": _type12(stem),
        "realization_index": ridx,
        "controllers": {},
    }
    base = _controllers(
        case,
        arrival=pack.arrival,
        finite=pack.finite,
        pol=pol,
        budget=BUDGET,
        include_ablations=False,
    )
    cell["controllers"]["cce_greedy_nominal"] = _run(
        case, base["cce_greedy_nominal"], "cce_greedy_nominal"
    )
    cell["controllers"]["css_spi"] = _run(
        case,
        make_proposed_mpc(
            case,
            cfg=cfg,
            pack=pack,
            pol=pol,
            budget=BUDGET,
            alns_iterations=ALNS_ITER,
            n_scenarios=int(cfg["n_scenarios"]),
            rollout_max_events=100,
        ),
        "css_spi",
    )
    cell["cell_wall_seconds"] = time.perf_counter() - t_cell
    return cell


def _write(payload: dict) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    s = payload.get("summary") or {}
    prop = s.get("proposed_means") or {}
    gn = s.get("gn_means") or {}
    lines = [
        "# Schneider full-instance results",
        "",
        f"**Protocol:** `{PROTOCOL}`",
        f"**Instances:** {s.get('n_stems')} stems, {s.get('n_cells')} cells",
        f"**Stack:** recovery forecast + M1–M4",
        f"**Workers:** {(payload.get('compute') or {}).get('n_workers')}",
        "",
        "## Proposed vs GN (means)",
        "",
        "| Metric | Proposed | GN |",
        "|---|---|---|",
    ]
    for k in METRIC_KEYS:
        pm = (prop.get(k) or {}).get("mean")
        gm = (gn.get(k) or {}).get("mean")
        lines.append(f"| {k} | {pm} | {gm} |")
    lines.extend(
        [
            "",
            "## Gates",
            f"- Gate: {payload.get('gate')}",
            f"- Formal NI: {payload.get('formal_ni')}",
            f"- Paired ΔJ: {payload.get('paired_vs_gn_j')}",
            f"- Paired ΔAU: {payload.get('paired_vs_gn_au')}",
            f"- Paired Δdistance: {payload.get('paired_vs_gn_distance')}",
            f"- Paired Δservice_rate: {payload.get('paired_vs_gn_service_rate')}",
            f"- Paired Δcharge_time: {payload.get('paired_vs_gn_charge_time')}",
            "",
            "## By size",
            "",
        ]
    )
    for size, block in sorted((payload.get("by_size") or {}).items(), key=lambda kv: int(kv[0])):
        lines.append(f"### size={size}")
        lines.append(f"- n_cells: {block.get('n_cells')}")
        lines.append(f"- mean ΔJ: {(block.get('paired_j', {}).get('delta') or {}).get('mean')}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_schneider_full(*, resume: bool = True, n_workers: int = DEFAULT_WORKERS) -> dict:
    cfg = _method_cfg()
    refs = list_schneider_refs()
    refs = sorted(refs, key=lambda r: (int(r.size_bucket), r.stem))
    stems = [r.stem for r in refs]
    size_of = {r.stem: int(r.size_bucket) for r in refs}
    total_plan = sum(N_REAL_100 if size_of[s] >= 100 else N_REAL_SMALL for s in stems)
    n_workers = max(1, int(n_workers))

    print(
        f"  [sch-full] start protocol={PROTOCOL} stems={len(stems)} "
        f"plan_cells~{total_plan} workers={n_workers}",
        flush=True,
    )

    payload: dict = {
        "protocol": PROTOCOL,
        "scientific_identity": (
            "commitment-safe RH MPC + SPI + M1-M4 + Schneider-fit forecast; "
            "full-instance Schneider campaign with rich ops metrics"
        ),
        "compute": {
            "budget": BUDGET,
            "alns_iterations": ALNS_ITER,
            "n_scenarios": cfg["n_scenarios"],
            "n_realizations_small": N_REAL_SMALL,
            "n_realizations_100": N_REAL_100,
            "n_workers": n_workers,
            "parallel": n_workers > 1,
        },
        "method_stack": cfg,
        "stems": stems,
        "rows": [],
        "summary": {},
    }
    done_keys: set[tuple[str, int]] = set()
    if resume and OUT_JSON.exists():
        try:
            prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
            if prev.get("protocol") == PROTOCOL and isinstance(prev.get("rows"), list):
                payload["rows"] = list(prev["rows"])
                for row in payload["rows"]:
                    done_keys.add((row["stem"], int(row["realization_index"])))
                print(f"  resume: {len(done_keys)} cells already done", flush=True)
        except json.JSONDecodeError:
            pass

    jobs: list[dict] = []
    for stem in stems:
        n_real = N_REAL_100 if size_of[stem] >= 100 else N_REAL_SMALL
        for ridx in range(n_real):
            if (stem, ridx) in done_keys:
                continue
            jobs.append(
                {
                    "stem": stem,
                    "realization_index": ridx,
                    "size_bucket": size_of[stem],
                    "cfg": cfg,
                }
            )

    t0 = time.perf_counter()
    done = len(done_keys)
    print(f"  [sch-full] pending={len(jobs)} already={done}", flush=True)

    if not jobs:
        return _finalize(payload, t0)

    if n_workers == 1:
        for job in jobs:
            print(
                f"  [sch-full] begin {done + 1}/{total_plan} {job['stem']} "
                f"r{job['realization_index']} size={job['size_bucket']}",
                flush=True,
            )
            cell = _eval_cell(job)
            payload["rows"].append(cell)
            done += 1
            done_keys.add((cell["stem"], int(cell["realization_index"])))
            _checkpoint_partial(payload, t0)
            print(
                f"  [sch-full] {done}/{total_plan} {cell['stem']} r{cell['realization_index']} "
                f"size={cell['size_bucket']} cell={cell.get('cell_wall_seconds', 0):.0f}s "
                f"({time.perf_counter() - t0:.0f}s)",
                flush=True,
            )
        return _finalize(payload, t0)

    # Parallel: same cells, independent processes.
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_eval_cell, job): job for job in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                cell = fut.result()
            except Exception as exc:  # noqa: BLE001 — keep campaign alive; record failure cell
                print(
                    f"  [sch-full] FAIL {job['stem']} r{job['realization_index']}: {exc!r}",
                    flush=True,
                )
                cell = {
                    "dataset": "schneider_evrptw",
                    "stem": job["stem"],
                    "size_bucket": job["size_bucket"],
                    "family": (
                        "rc"
                        if job["stem"].lower().startswith("rc")
                        else ("r" if job["stem"].lower().startswith("r") else "c")
                    ),
                    "type12": _type12(job["stem"]),
                    "realization_index": job["realization_index"],
                    "controllers": {
                        "cce_greedy_nominal": {"failure": repr(exc)},
                        "css_spi": {"failure": repr(exc)},
                    },
                    "cell_wall_seconds": None,
                }
            payload["rows"].append(cell)
            done += 1
            done_keys.add((cell["stem"], int(cell["realization_index"])))
            _checkpoint_partial(payload, t0)
            print(
                f"  [sch-full] {done}/{total_plan} {cell['stem']} r{cell['realization_index']} "
                f"size={cell['size_bucket']} cell={cell.get('cell_wall_seconds', 0)} "
                f"({time.perf_counter() - t0:.0f}s) [x{n_workers}]",
                flush=True,
            )

    return _finalize(payload, t0)


def _checkpoint_partial(payload: dict, t0: float) -> None:
    payload["summary"] = {
        "n_cells": len(payload["rows"]),
        "n_stems": len({r["stem"] for r in payload["rows"]}),
        "wall_seconds_so_far": time.perf_counter() - t0,
        "partial": True,
        "n_workers": (payload.get("compute") or {}).get("n_workers"),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _finalize(payload: dict, t0: float) -> dict:
    rows = payload["rows"]
    paired_j = _paired_clustered(rows, "css_spi", "cce_greedy_nominal", PRIMARY)
    paired_au = _paired_clustered(
        rows, "css_spi", "cce_greedy_nominal", "accepted_unfulfilled_count"
    )
    paired_dist = _paired_clustered(rows, "css_spi", "cce_greedy_nominal", "executed_distance")
    paired_sr = _paired_clustered(rows, "css_spi", "cce_greedy_nominal", "service_rate")
    paired_ch = _paired_clustered(rows, "css_spi", "cce_greedy_nominal", "executed_charge_time")
    gate = evaluate_gate({"css_spi_vs_gn_economic": paired_j, "css_spi_vs_gn_au": paired_au})
    by_size: dict[str, dict] = {}
    groups: dict[int, list] = defaultdict(list)
    for r in rows:
        groups[int(r["size_bucket"])].append(r)
    for size, sub in groups.items():
        by_size[str(size)] = {
            "n_cells": len(sub),
            "paired_j": _paired_clustered(sub, "css_spi", "cce_greedy_nominal", PRIMARY),
            "proposed_means": _means(sub, "css_spi"),
            "gn_means": _means(sub, "cce_greedy_nominal"),
        }
    payload.update(
        {
            "wall_seconds": time.perf_counter() - t0,
            "gate": gate,
            "formal_ni": _formal_ni(paired_j),
            "paired_vs_gn_j": paired_j,
            "paired_vs_gn_au": paired_au,
            "paired_vs_gn_distance": paired_dist,
            "paired_vs_gn_service_rate": paired_sr,
            "paired_vs_gn_charge_time": paired_ch,
            "by_size": by_size,
            "summary": {
                "n_stems": len({r["stem"] for r in rows}),
                "n_cells": len(rows),
                "partial": False,
                "proposed_means": _means(rows, "css_spi"),
                "gn_means": _means(rows, "cce_greedy_nominal"),
                "gate_pass": gate.get("pass"),
                "ni_pass": _formal_ni(paired_j).get("pass"),
                "mean_dj": (paired_j.get("delta") or {}).get("mean"),
            },
        }
    )
    _write(payload)
    print(json.dumps(payload["summary"], indent=2), flush=True)
    return payload


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--no-resume", action="store_true")
    p.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel cell workers (default 8). Same results as serial.",
    )
    args = p.parse_args()
    run_schneider_full(resume=not args.no_resume, n_workers=args.workers)


if __name__ == "__main__":
    main()
