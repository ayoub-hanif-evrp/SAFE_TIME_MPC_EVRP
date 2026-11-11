"""Classify frontier episodes with accepted_unfulfilled using explicit termination reasons."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_frontier_suite
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.validation.replay import validate_log


def _controller_factory(name: str, case, *, budget: float, seed: int, iterations: int):
    from safe_time_evrp.commitment_safe_mpc.budget_frontier import _controller_factory as factory

    return factory(name, case, budget=budget, seed=seed, iterations=iterations)


def classify_episode(case, controller_name: str, *, budget: float, seed: int, iterations: int = 80) -> dict:
    ctrl = _controller_factory(controller_name, case, budget=budget, seed=seed, iterations=iterations)
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
    term = result.termination_reason
    pending = result.pending_next_event_time
    nfc = result.no_feasible_continuation_count

    # Attribution uses explicit termination_reason; NFC co-occurrence is recorded separately.
    if not au:
        label = "no_accepted_unfulfilled"
    elif term == "cutoff_next_event_after_tmax":
        label = "cutoff_censor_with_accepted_unfulfilled"
    elif term == "natural_completion" and au:
        label = "natural_end_with_accepted_unfulfilled"
    elif term == "no_pending_events" and au:
        label = "no_events_with_accepted_unfulfilled"
    else:
        label = f"residual_accepts_term_{term}"

    # Secondary flags (not primary causal proof).
    flags = []
    if nfc > 0:
        flags.append("had_no_feasible_continuation_decisions")
    if pending is not None and result.t_max is not None and pending > result.t_max + EPS:
        flags.append("pending_event_after_tmax")
    if end_time + EPS >= case.t_max:
        flags.append("last_log_time_ge_tmax")  # informational only; not a terminator

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
        "termination_reason": term,
        "pending_next_event_time": pending,
        "no_feasible_continuation_count": nfc,
        "label": label,
        "flags": flags,
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
            "Labels use EpisodeResult.termination_reason. "
            "Co-occurrence with no_feasible_continuation is a flag, not proof of causation. "
            "end_time >= t_max alone is not used as the cutoff test."
        ),
        "rows": classified,
    }


if __name__ == "__main__":
    art = audit_frontier_unfulfilled()
    out = Path("docs/mpc_central/fulfillment_audit.json")
    out.write_text(json.dumps(art, indent=2), encoding="utf-8")
    print(json.dumps({"n_audited": art["n_audited"], "label_counts": art["label_counts"]}, indent=2))
