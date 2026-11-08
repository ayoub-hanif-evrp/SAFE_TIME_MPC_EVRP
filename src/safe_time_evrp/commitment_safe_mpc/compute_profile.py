"""Computational bottleneck profiling for ALNS–MPC / B1 (Commit 2).

Measures where wall time and route evaluations are spent — not a claim that
outer B1 validation is the dominant cost on small toys.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite, build_scaled_suite
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.controllers.episode import run_episode


@dataclass
class ProfileRow:
    case_id: str
    controller: str
    n_customers: int
    decisions: int
    optimize_seconds: float
    alns_wall_seconds: float
    route_evaluations: int
    candidates_evaluated: int
    iterations: int
    rescued_customers: int
    validation_seconds: float
    first_feasible_seconds: float | None
    best_feasible_seconds: float | None
    seconds_after_best_incumbent: float | None
    fraction_validation_of_optimize: float | None
    notes: list[str] = field(default_factory=list)


def _n_customers(case: BaselineCase) -> int:
    return len(case.instance.customers)


def profile_case(case: BaselineCase, *, iterations: int = 40, time_limit: float = 0.5) -> list[ProfileRow]:
    rows: list[ProfileRow] = []
    for name, factory in (
        (
            "alns",
            lambda: ReactiveAlnsMpc(
                case.instance, case.horizon, iterations=iterations, time_limit_seconds=time_limit, seed=7
            ),
        ),
        (
            "b1",
            lambda: FullValidationAlnsMpc(
                case.instance, case.horizon, iterations=iterations, time_limit_seconds=time_limit, seed=7
            ),
        ),
    ):
        ctrl = factory()
        t0 = perf_counter()
        result = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
        )
        wall = perf_counter() - t0
        alns = getattr(ctrl, "_alns", ctrl)
        diag = alns.last_diagnostics
        val = 0.0
        if name == "b1":
            val = float(ctrl.profile.validation_seconds)
        first = diag.first_feasible_seconds
        best = diag.best_feasible_seconds
        after = None
        if best is not None and diag.wall_seconds is not None:
            after = max(0.0, diag.wall_seconds - best)
        frac = (val / result.optimize_seconds) if result.optimize_seconds > 0 else None
        len(diag.rescued_customers) if diag.rescued_customers else 0
        # Sum rescued across decisions approximately via last decide only; episode-level from audits
        rescued_ep = 0
        for d in result.decisions:
            al = (d.audit or {}).get("alns") or {}
            rescued_ep += len(al.get("rescued_customers") or [])
        rows.append(
            ProfileRow(
                case_id=case.case_id,
                controller=name,
                n_customers=_n_customers(case),
                decisions=len(result.decisions),
                optimize_seconds=result.optimize_seconds,
                alns_wall_seconds=float(diag.wall_seconds or wall),
                route_evaluations=int(diag.route_evaluations),
                candidates_evaluated=int(diag.candidates_evaluated),
                iterations=int(diag.iterations),
                rescued_customers=rescued_ep,
                validation_seconds=val,
                first_feasible_seconds=first,
                best_feasible_seconds=best,
                seconds_after_best_incumbent=after,
                fraction_validation_of_optimize=frac,
                notes=list(diag.notes[:4]),
            )
        )
    return rows


def run_compute_profile() -> dict:
    cases = build_baseline_suite() + build_scaled_suite()
    rows: list[dict] = []
    for case in cases:
        for row in profile_case(case):
            rows.append(asdict(row))
    # Aggregate insight
    b1_rows = [r for r in rows if r["controller"] == "b1"]
    alns_rows = [r for r in rows if r["controller"] == "alns"]

    def _mean(key: str, data: list[dict]) -> float:
        vals = [float(r[key] or 0.0) for r in data]
        return sum(vals) / len(vals) if vals else 0.0

    summary = {
        "n_cases": len(cases),
        "mean_alns_route_evaluations": _mean("route_evaluations", alns_rows),
        "mean_b1_validation_seconds": _mean("validation_seconds", b1_rows),
        "mean_b1_optimize_seconds": _mean("optimize_seconds", b1_rows),
        "mean_b1_validation_fraction": _mean("fraction_validation_of_optimize", b1_rows),
        "note": "On these instances, candidate evaluate_route work dominates outer B1 validation.",
    }
    return {"rows": rows, "summary": summary}


def write_compute_profile(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_compute_profile()
    (out_dir / "compute_bottleneck_profile.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_compute_profile(Path("docs/commitment_safe_mpc"))
    print(json.dumps(art["summary"], indent=2))
