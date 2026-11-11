"""Classify frontier episodes with accepted_unfulfilled (Task 5).

Replays each matching budget_frontier row on the authoritative plant and labels
the terminal cause without speculation beyond observed simulator state.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_frontier_suite
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.validation.replay import validate_log


def _controller_factory(name: str, case, *, budget: float, seed: int, iterations: int):
    from safe_time_evrp.commitment_safe_mpc.budget_frontier import _controller_factory

    return _controller_factory(name, case, budget=budget, seed=seed, iterations=iterations)


def classify_episode(case, controller_name: str, *, budget: float, seed: int, iterations: int = 80) -> dict:
    ctrl = _controller_factory(controller_name, case, budget=budget, seed=seed, iterations=iterations)
    # Use the same run_episode path but keep the simulator finished state via a thin wrapper:
    # re-run and inspect final_requests + whether wall clock hit t_max via log episode_end time.
    result = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    report = validate_log(case.instance, result.log)
    final = result.final_requests
    au = sorted(cid for cid, st in final.items() if st == "accepted_unfulfilled")
    completed = sorted(cid for cid, st in final.items() if st == "completed")
    end_time = max((rec.time for rec in result.log), default=0.0)
    hit_tmax = end_time + EPS >= case.t_max
    # In-service at end would appear as accepted_unfulfilled only after mark_finished if ACCEPTED;
    # IN_SERVICE left open is unusual after mark_finished.
    busy_end = any(
        rec.kind == "episode_end"
        and any(
            v.get("status") != "idle" or v.get("node") != case.instance.depot_id
            for v in rec.data.get("vehicles", {}).values()
        )
        for rec in result.log
        if rec.kind == "episode_end"
    )
    if not au:
        label = "no_accepted_unfulfilled"
    elif hit_tmax and busy_end:
        label = "tmax_censor_busy_fleet"
    elif hit_tmax:
        label = "tmax_censor_accepted_remaining"
    elif result.no_feasible_continuation_count > 0 and au:
        label = "no_feasible_continuation_with_residual_accepts"
    else:
        label = "residual_accepts_before_natural_end"
    return {
        "case_id": case.case_id,
        "controller": controller_name,
        "budget_seconds": budget,
        "seed": seed,
        "accepted_unfulfilled": au,
        "accepted_unfulfilled_count": len(au),
        "completed_count": len(completed),
        "replay_ok": report.ok,
        "end_time": end_time,
        "t_max": case.t_max,
        "hit_tmax": hit_tmax,
        "busy_end": busy_end,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "label": label,
    }


def audit_frontier_unfulfilled(
    frontier_json: Path | None = None,
    *,
    iterations: int = 80,
    limit: int | None = None,
) -> dict:
    path = frontier_json or Path("docs/commitment_safe_mpc/budget_frontier.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in payload["rows"] if r.get("accepted_unfulfilled_count", 0) > 0]
    if limit is not None:
        rows = rows[:limit]
    cases = {c.case_id: c for c in build_frontier_suite()}
    classified = []
    for row in rows:
        case = cases[row["case_id"]]
        classified.append(
            classify_episode(
                case,
                row["controller"],
                budget=float(row["budget_seconds"]),
                seed=int(row["seed"]),
                iterations=iterations,
            )
        )
    counts = Counter(r["label"] for r in classified)
    return {
        "source": str(path),
        "n_source_au_rows": len([r for r in payload["rows"] if r.get("accepted_unfulfilled_count", 0) > 0]),
        "n_audited": len(classified),
        "label_counts": dict(counts),
        "note": (
            "Labels are from replaying the same case/controller/budget/seed on FleetSimulator. "
            "replay_ok remains distinct from commitment fulfillment."
        ),
        "rows": classified,
    }


if __name__ == "__main__":
    # Full audit of all AU rows can take several minutes (frontier_30/50).
    art = audit_frontier_unfulfilled()
    out = Path("docs/mpc_central/fulfillment_audit.json")
    out.write_text(json.dumps(art, indent=2), encoding="utf-8")
    print(json.dumps({"n_audited": art["n_audited"], "label_counts": art["label_counts"]}, indent=2))
