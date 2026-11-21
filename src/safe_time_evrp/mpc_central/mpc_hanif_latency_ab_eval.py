"""Hanif / Homberger A+B latency appendix — protocol ``mpc_hanif_latency_ab_v1``.

≤2h wall package: full A+B at cap=25 + stratified cap curve.
Not a closed-loop J ranking (1000-customer episodes stall).
"""

from __future__ import annotations

import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from safe_time_evrp.data.homberger_charging import (
    homberger_family,
    list_variant_a_instances,
    list_variant_b_instances,
    parse_homberger_evrptw,
)
from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.testbed.constructor import make_observation

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_HANIF_LATENCY_AB_RESULTS.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_HANIF_LATENCY_AB_RESULTS.md"
SPLITS = ROOT / "docs" / "experiments" / "MPC_HANIF_LATENCY_AB_SPLITS.json"
PROTOCOL = "mpc_hanif_latency_ab_v1"

BUDGET = 2.0
N_DECIDES = 5
PRIMARY_CAP = 25
CURVE_CAPS = (25, 50, 100, 200)
FAMILIES = ("C1", "C2", "R1", "R2", "RC1", "RC2")
DEFAULT_WORKERS = 8
ALNS_ITER = 10


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


def _capped_obs(inst, *, announced_cap: int, fleet_size: int = 4):
    cust = inst.customer_ids()[: int(announced_cap)]
    obs0 = make_observation(inst, fleet_size=fleet_size, start_time=0.0)
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
    return Observation(
        0.0,
        tuple(vehicles),
        tuple(cust),
        (),
        (),
        (),
        (),
        (),
        public_customer_count=len(inst.customer_ids()),
    ), cust


def _controllers(inst, horizon: float, pol: int):
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=BUDGET,
        seed=int(pol),
        max_replan_interval=25.0,
        rollout_max_events=60,
    )
    proposed = CommitmentSafeStochasticMpc(
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
        accept_score_penalty=50.0,
        charge_first_soc_frac=0.2,
        selection_mode="mean_score",
        scenario_sample_mode="stratified",
        adaptive_compute=True,
        n_scenarios_max=4,
        alns_iterations_max=20,
        **common,
    )
    gn = CertificateCarryingEconomicMpc(
        inst,
        horizon,
        forecast=None,
        n_scenarios=1,
        use_forecast=False,
        scoring_mode="greedy_nominal",
        use_persistent_certificate=True,
        **common,
    )
    return {"css_spi": proposed, "cce_greedy_nominal": gn}


def _bench_cell(job: dict) -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

    path = Path(job["path"])
    cap = int(job["announced_cap"])
    t0 = time.perf_counter()
    inst = parse_homberger_evrptw(path)
    depot_due = float(inst.node(inst.depot_id).window.due)
    horizon = min(depot_due, 400.0)
    obs, cust = _capped_obs(inst, announced_cap=cap)
    ctrls = _controllers(inst, horizon, pol=5)
    cell = {
        "dataset": "evrptw_homberger_charging",
        "variant": job["variant"],
        "stem": path.stem,
        "family": homberger_family(path.stem),
        "announced_cap": cap,
        "n_customers_announced": len(cust),
        "n_customers_instance": len(inst.customer_ids()),
        "bench": "timed_decide_only",
        "block": job["block"],
        "controllers": {},
    }
    for name, ctrl in ctrls.items():
        times: list[float] = []
        failure = None
        tw0 = time.perf_counter()
        try:
            for i in range(N_DECIDES):
                d = ctrl.decide(obs, "request_release" if i == 0 else "replan_interval")
                times.append(float(d.optimize_seconds or 0.0))
        except Exception as exc:  # noqa: BLE001
            failure = f"{type(exc).__name__}:{exc}"
        cell["controllers"][name] = {
            "controller": name,
            "failure": failure,
            "decide_seconds": times,
            "latency": _latency(times),
            "wall_seconds": time.perf_counter() - tw0,
            "n_hard_fail": 1 if failure else 0,
        }
    cell["cell_wall_seconds"] = time.perf_counter() - t0
    return cell


def _stratified_curve_files() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for variant, files in (
        ("A", list_variant_a_instances()),
        ("B", list_variant_b_instances()),
    ):
        by_fam: dict[str, list[Path]] = {f: [] for f in FAMILIES}
        for p in files:
            fam = homberger_family(p.stem)
            if fam in by_fam:
                by_fam[fam].append(p)
        for fam in FAMILIES:
            if by_fam[fam]:
                out.append((variant, by_fam[fam][0]))
    return out


def _agg_ctrl(rows: list[dict], ctrl: str) -> dict:
    times: list[float] = []
    fails = 0
    for r in rows:
        c = (r.get("controllers") or {}).get(ctrl) or {}
        if c.get("failure"):
            fails += 1
        times.extend(list(c.get("decide_seconds") or []))
    lat = _latency(times)
    return {
        "n_cells": len(rows),
        "n_hard_fails": fails,
        "latency": lat,
        "p50_under_budget": (lat.get("p50") is not None and lat["p50"] <= BUDGET),
    }


def _write(payload: dict) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    s = payload.get("summary") or {}
    lines = [
        "# Hanif / Homberger A+B latency results",
        "",
        f"**Protocol:** `{PROTOCOL}`",
        f"**Wall hours:** {round((payload.get('wall_seconds') or 0) / 3600, 3)}",
        f"**Workers:** {(payload.get('compute') or {}).get('n_workers')}",
        "",
        "## Primary (cap=25, all A+B)",
        f"- n_cells: {s.get('n_primary')}",
        f"- Proposed: {s.get('primary_proposed')}",
        f"- GN: {s.get('primary_gn')}",
        f"- Pass (0 hard fails + proposed p50≤2.0): **{s.get('pass')}**",
        "",
        "### By variant",
    ]
    for v, block in sorted((s.get("by_variant") or {}).items()):
        lines.append(f"- **{v}:** proposed p50={((block.get('css_spi') or {}).get('latency') or {}).get('p50')} "
                     f"fails={((block.get('css_spi') or {}).get('n_hard_fails'))}")
    lines.extend(["", "## Cap curve (stratified 12 files)", ""])
    for cap, block in sorted((s.get("curve_by_cap") or {}).items(), key=lambda kv: int(kv[0])):
        pp = ((block.get("css_spi") or {}).get("latency") or {}).get("p50")
        pf = (block.get("css_spi") or {}).get("n_hard_fails")
        lines.append(f"- cap={cap}: proposed p50={pp}, hard_fails={pf}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_hanif_latency_ab(*, n_workers: int = DEFAULT_WORKERS) -> dict:
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))
    n_workers = max(1, int(n_workers))
    jobs: list[dict] = []

    for variant, files in (
        ("A", list_variant_a_instances()),
        ("B", list_variant_b_instances()),
    ):
        for p in files:
            jobs.append(
                {
                    "path": str(p),
                    "variant": variant,
                    "announced_cap": PRIMARY_CAP,
                    "block": "primary",
                }
            )

    for variant, p in _stratified_curve_files():
        for cap in CURVE_CAPS:
            if cap == PRIMARY_CAP:
                # Already covered in primary for these stems; still re-bench for curve block purity.
                pass
            jobs.append(
                {
                    "path": str(p),
                    "variant": variant,
                    "announced_cap": cap,
                    "block": "curve",
                }
            )

    print(
        f"  [hanif] start protocol={PROTOCOL} jobs={len(jobs)} "
        f"(primary={120}, curve={len(_stratified_curve_files()) * len(CURVE_CAPS)}) workers={n_workers}",
        flush=True,
    )

    payload: dict = {
        "protocol": PROTOCOL,
        "scientific_identity": (
            "Hanif/Homberger charging latency appendix: CSS-MPC M1-M4 empty-future "
            "(no transferred Schneider forecast) vs greedy-nominal CCE"
        ),
        "splits_ref": str(SPLITS.relative_to(ROOT)).replace("\\", "/"),
        "method_stack": splits.get("method_stack"),
        "compute": {
            "budget": BUDGET,
            "n_decides": N_DECIDES,
            "primary_cap": PRIMARY_CAP,
            "curve_caps": list(CURVE_CAPS),
            "n_workers": n_workers,
        },
        "rows": [],
        "summary": {},
    }

    t0 = time.perf_counter()
    done = 0
    if n_workers == 1:
        for job in jobs:
            cell = _bench_cell(job)
            payload["rows"].append(cell)
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"  [hanif] {done}/{len(jobs)} ({time.perf_counter() - t0:.0f}s)", flush=True)
                _checkpoint(payload, t0)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futs = {pool.submit(_bench_cell, job): job for job in jobs}
            for fut in as_completed(futs):
                job = futs[fut]
                try:
                    cell = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"  [hanif] FAIL {job['path']} cap={job['announced_cap']}: {exc!r}", flush=True)
                    cell = {
                        "dataset": "evrptw_homberger_charging",
                        "variant": job["variant"],
                        "stem": Path(job["path"]).stem,
                        "family": homberger_family(Path(job["path"]).stem),
                        "announced_cap": job["announced_cap"],
                        "bench": "timed_decide_only",
                        "block": job["block"],
                        "controllers": {
                            "css_spi": {"failure": repr(exc), "n_hard_fail": 1, "decide_seconds": []},
                            "cce_greedy_nominal": {
                                "failure": repr(exc),
                                "n_hard_fail": 1,
                                "decide_seconds": [],
                            },
                        },
                    }
                payload["rows"].append(cell)
                done += 1
                if done % 10 == 0 or done == len(jobs):
                    print(
                        f"  [hanif] {done}/{len(jobs)} ({time.perf_counter() - t0:.0f}s) [x{n_workers}]",
                        flush=True,
                    )
                    _checkpoint(payload, t0)

    return _finalize(payload, t0)


def _checkpoint(payload: dict, t0: float) -> None:
    payload["summary"] = {
        "partial": True,
        "n_cells": len(payload["rows"]),
        "wall_seconds_so_far": time.perf_counter() - t0,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _finalize(payload: dict, t0: float) -> dict:
    rows = payload["rows"]
    primary = [r for r in rows if r.get("block") == "primary"]
    curve = [r for r in rows if r.get("block") == "curve"]
    prop = _agg_ctrl(primary, "css_spi")
    gn = _agg_ctrl(primary, "cce_greedy_nominal")
    by_variant: dict[str, dict] = {}
    for v in ("A", "B"):
        sub = [r for r in primary if r.get("variant") == v]
        by_variant[v] = {
            "css_spi": _agg_ctrl(sub, "css_spi"),
            "cce_greedy_nominal": _agg_ctrl(sub, "cce_greedy_nominal"),
        }
    curve_by_cap: dict[str, dict] = {}
    for cap in CURVE_CAPS:
        sub = [r for r in curve if int(r.get("announced_cap") or 0) == cap]
        curve_by_cap[str(cap)] = {
            "css_spi": _agg_ctrl(sub, "css_spi"),
            "cce_greedy_nominal": _agg_ctrl(sub, "cce_greedy_nominal"),
        }
    passed = (
        prop.get("n_hard_fails", 1) == 0
        and gn.get("n_hard_fails", 1) == 0
        and bool(prop.get("p50_under_budget"))
    )
    payload["wall_seconds"] = time.perf_counter() - t0
    payload["summary"] = {
        "partial": False,
        "n_primary": len(primary),
        "n_curve": len(curve),
        "primary_proposed": prop,
        "primary_gn": gn,
        "by_variant": by_variant,
        "curve_by_cap": curve_by_cap,
        "pass": passed,
        "pass_rules": {
            "zero_hard_fails": prop.get("n_hard_fails") == 0 and gn.get("n_hard_fails") == 0,
            "proposed_p50_le_budget": prop.get("p50_under_budget"),
            "budget": BUDGET,
        },
    }
    _write(payload)
    print(json.dumps(payload["summary"]["pass_rules"], indent=2), flush=True)
    print(f"  [hanif] PASS={passed} wall_s={payload['wall_seconds']:.1f}", flush=True)
    return payload


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = p.parse_args()
    run_hanif_latency_ab(n_workers=args.workers)


if __name__ == "__main__":
    main()
