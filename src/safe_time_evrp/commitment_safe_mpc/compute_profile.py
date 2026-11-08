"""Computational bottleneck profiling — aggregates ALL decision audits in an episode."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite, build_scaled_suite
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.route_resource_profile import EvalMode
from safe_time_evrp.controllers.episode import run_episode


@dataclass
class ProfileRow:
    case_id: str
    controller: str
    n_customers: int
    decisions: int
    optimize_seconds: float
    route_evaluations: int
    candidates_evaluated: int
    iterations: int
    rescued_customers: int
    validation_seconds: float
    evaluate_route_calls: int
    full_calls_avoided: int
    prefix_visits_reused: int
    suffix_visits_recomputed: int
    incremental_evals: int
    full_evals: int
    fraction_validation_of_optimize: float | None
    notes: list[str] = field(default_factory=list)


def _n_customers(case: BaselineCase) -> int:
    return len(case.instance.customers)


def _aggregate_audits(result) -> dict:
    route_evaluations = 0
    candidates = 0
    iterations = 0
    rescued = 0
    validation = 0.0
    evaluate_route_calls = 0
    full_calls_avoided = 0
    prefix_visits_reused = 0
    suffix_visits_recomputed = 0
    incremental_evals = 0
    full_evals = 0
    for d in result.decisions:
        audit = d.audit or {}
        alns = audit.get("alns") or {}
        route_evaluations += int(alns.get("route_evaluations") or 0)
        candidates += int(alns.get("candidates_evaluated") or 0)
        iterations += int(alns.get("iterations") or 0)
        rescued += len(alns.get("rescued_customers") or [])
        validation += float(
            audit.get("validation_seconds_this_decision")
            if audit.get("validation_seconds_this_decision") is not None
            else audit.get("validation_seconds") or 0.0
        )
        stats = alns.get("eval_stats") or {}
        evaluate_route_calls += int(stats.get("evaluate_route_calls") or 0)
        full_calls_avoided += int(stats.get("full_calls_avoided") or 0)
        prefix_visits_reused += int(stats.get("prefix_visits_reused") or 0)
        suffix_visits_recomputed += int(stats.get("suffix_visits_recomputed") or 0)
        incremental_evals += int(stats.get("incremental_evals") or 0)
        full_evals += int(stats.get("full_evals") or 0)
    return {
        "route_evaluations": route_evaluations,
        "candidates_evaluated": candidates,
        "iterations": iterations,
        "rescued_customers": rescued,
        "validation_seconds": validation,
        "evaluate_route_calls": evaluate_route_calls,
        "full_calls_avoided": full_calls_avoided,
        "prefix_visits_reused": prefix_visits_reused,
        "suffix_visits_recomputed": suffix_visits_recomputed,
        "incremental_evals": incremental_evals,
        "full_evals": full_evals,
    }


def profile_case(case: BaselineCase, *, iterations: int = 40, time_limit: float = 0.5) -> list[ProfileRow]:
    rows: list[ProfileRow] = []
    factories = [
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
        (
            "m1",
            lambda: CertificateCarryingAlnsMpc(
                case.instance,
                case.horizon,
                iterations=iterations,
                time_limit_seconds=time_limit,
                seed=7,
                eval_mode=EvalMode.INCREMENTAL_EVALUATION,
                reuse_certificates=True,
            ),
        ),
    ]
    for name, factory in factories:
        ctrl = factory()
        result = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
        )
        agg = _aggregate_audits(result)
        frac = (agg["validation_seconds"] / result.optimize_seconds) if result.optimize_seconds > 0 else None
        rows.append(
            ProfileRow(
                case_id=case.case_id,
                controller=name,
                n_customers=_n_customers(case),
                decisions=len(result.decisions),
                optimize_seconds=result.optimize_seconds,
                fraction_validation_of_optimize=frac,
                notes=[],
                **agg,
            )
        )
    return rows


def run_compute_profile() -> dict:
    cases = build_baseline_suite() + build_scaled_suite()
    rows: list[dict] = []
    for case in cases:
        for row in profile_case(case):
            rows.append(asdict(row))

    def _mean(key: str, data: list[dict]) -> float:
        vals = [float(r[key] or 0.0) for r in data]
        return sum(vals) / len(vals) if vals else 0.0

    b1 = [r for r in rows if r["controller"] == "b1"]
    m1 = [r for r in rows if r["controller"] == "m1"]
    alns = [r for r in rows if r["controller"] == "alns"]
    summary = {
        "n_cases": len(cases),
        "mean_alns_route_evaluations_episode": _mean("route_evaluations", alns),
        "mean_b1_validation_seconds": _mean("validation_seconds", b1),
        "mean_b1_optimize_seconds": _mean("optimize_seconds", b1),
        "mean_m1_optimize_seconds": _mean("optimize_seconds", m1),
        "mean_m1_full_calls_avoided": _mean("full_calls_avoided", m1),
        "mean_m1_evaluate_route_calls": _mean("evaluate_route_calls", m1),
        "mean_m1_suffix_visits_recomputed": _mean("suffix_visits_recomputed", m1),
        "note": "Totals aggregated from every decision audit, not the last decide() only.",
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
