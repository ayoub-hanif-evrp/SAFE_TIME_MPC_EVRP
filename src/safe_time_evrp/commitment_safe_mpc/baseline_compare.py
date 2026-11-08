"""Matched comparison: insertion MPC vs reactive ALNS–MPC (B0)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.validation.replay import validate_log


@dataclass
class ControllerEpisodeStats:
    controller: str
    case_id: str
    completed: list[str]
    accepted_final: list[str]
    accepted_unfulfilled: list[str]
    rejected: list[str]
    n_charge_starts: int
    n_replans: int
    total_distance: float
    optimize_seconds: float
    mean_decision_seconds: float
    no_feasible_continuation_count: int
    replay_ok: bool
    alns_improvements: int | None = None
    alns_iterations: int | None = None
    alns_improved_over_constructor: bool | None = None
    alns_candidates: int | None = None


def _summarize(case: BaselineCase, controller_name: str, controller, result) -> ControllerEpisodeStats:
    report = validate_log(case.instance, result.log)
    charge_starts = sum(1 for r in result.log if r.kind == "charge_start")
    distances = [d.total_distance for d in result.decisions if d.total_distance]
    opt_times = [d.optimize_seconds for d in result.decisions]
    alns_imp = alns_it = alns_cand = None
    alns_beat = None
    if controller_name == "alns":
        imp = it = cand = 0
        beat = False
        for d in result.decisions:
            audit = (d.audit or {}).get("alns") or {}
            imp += int(audit.get("improvements") or 0)
            it += int(audit.get("iterations") or 0)
            cand += int(audit.get("candidates_evaluated") or 0)
            beat = beat or bool(audit.get("improved_over_constructor"))
        alns_imp, alns_it, alns_cand, alns_beat = imp, it, cand, beat
    final = result.final_requests
    return ControllerEpisodeStats(
        controller=controller_name,
        case_id=case.case_id,
        completed=[cid for cid, st in final.items() if st == "completed"],
        accepted_final=[
            cid for cid, st in final.items() if st in {"completed", "accepted", "in_service", "accepted_unfulfilled"}
        ],
        accepted_unfulfilled=[cid for cid, st in final.items() if st == "accepted_unfulfilled"],
        rejected=[cid for cid, st in final.items() if st == "rejected"],
        n_charge_starts=charge_starts,
        n_replans=len(result.decisions),
        total_distance=sum(distances),
        optimize_seconds=result.optimize_seconds,
        mean_decision_seconds=mean(opt_times) if opt_times else 0.0,
        no_feasible_continuation_count=result.no_feasible_continuation_count,
        replay_ok=report.ok,
        alns_improvements=alns_imp,
        alns_iterations=alns_it,
        alns_improved_over_constructor=alns_beat,
        alns_candidates=alns_cand,
    )


def run_matched_case(case: BaselineCase, *, alns_iterations: int = 30, alns_time: float = 0.2) -> dict:
    insertion = EventTriggeredMPC(case.instance, case.horizon)
    alns = ReactiveAlnsMpc(
        case.instance,
        case.horizon,
        iterations=alns_iterations,
        time_limit_seconds=alns_time,
        seed=7,
    )
    ins_res = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=insertion,
    )
    alns_res = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=alns,
    )
    return {
        "case_id": case.case_id,
        "tags": list(case.tags),
        "insertion": asdict(_summarize(case, "insertion", insertion, ins_res)),
        "alns": asdict(_summarize(case, "alns", alns, alns_res)),
    }


def run_baseline_study() -> dict:
    rows = [run_matched_case(case) for case in build_baseline_suite()]
    alns_search = sum(1 for r in rows if (r["alns"].get("alns_iterations") or 0) > 0)
    alns_improve = sum(1 for r in rows if r["alns"].get("alns_improvements"))
    replay_ok = sum(1 for r in rows if r["insertion"]["replay_ok"] and r["alns"]["replay_ok"])
    return {
        "rows": rows,
        "summary": {
            "n_cases": len(rows),
            "both_replay_ok": replay_ok,
            "alns_cases_with_search_iterations": alns_search,
            "alns_cases_with_improvements": alns_improve,
            "note": "ALNS need not dominate insertion on every case; search activity is required.",
        },
    }


def write_baseline_artifacts(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_baseline_study()
    (out_dir / "baseline_comparison.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_baseline_artifacts(Path("docs/commitment_safe_mpc"))
    print(json.dumps(art["summary"], indent=2))
    for row in art["rows"]:
        a, b = row["insertion"], row["alns"]
        print(
            row["case_id"],
            "ins_completed",
            len(a["completed"]),
            "alns_completed",
            len(b["completed"]),
            "alns_iters",
            b.get("alns_iterations"),
            "improvements",
            b.get("alns_improvements"),
            "replay",
            a["replay_ok"],
            b["replay_ok"],
        )
