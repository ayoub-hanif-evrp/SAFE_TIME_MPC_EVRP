"""Matched comparison: insertion MPC vs reactive ALNS–MPC (B0) [vs B1 when requested]."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import LogRecord
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
    executed_distance: float
    charged_energy: float
    executed_charge_time: float
    planned_distance_sum_diagnostic: float
    optimize_seconds: float
    mean_decision_seconds: float
    no_feasible_continuation_count: int
    replay_ok: bool
    alns_improvements: int | None = None
    alns_iterations: int | None = None
    alns_improved_over_constructor: bool | None = None
    alns_candidates: int | None = None
    validation_seconds: float | None = None
    certified_feasible_decisions: int | None = None


def executed_distance_from_log(instance: Instance, log: list[LogRecord]) -> float:
    """Sum physical depart arcs using the authoritative instance tables."""
    total = 0.0
    for record in log:
        if record.kind != "depart":
            continue
        origin = record.data["origin"]
        destination = record.data["destination"]
        if "distance" in record.data:
            total += float(record.data["distance"])
        else:
            total += instance.arc(origin, destination).distance
    return total


def charged_energy_and_time(log: list[LogRecord]) -> tuple[float, float]:
    energy = 0.0
    duration = 0.0
    for record in log:
        if record.kind == "charge_start":
            duration += float(record.data.get("duration", 0.0))
            # Energy gained ≈ target - soc when both logged
            if "target" in record.data and "soc" in record.data:
                energy += max(0.0, float(record.data["target"]) - float(record.data["soc"]))
        elif record.kind == "charge_end" and "energy" in record.data:
            energy += float(record.data["energy"])
    return energy, duration


def _summarize(case: BaselineCase, controller_name: str, result) -> ControllerEpisodeStats:
    report = validate_log(case.instance, result.log)
    charge_starts = sum(1 for r in result.log if r.kind == "charge_start")
    planned_sum = sum(d.total_distance for d in result.decisions if d.total_distance)
    opt_times = [d.optimize_seconds for d in result.decisions]
    exec_dist = executed_distance_from_log(case.instance, result.log)
    ch_e, ch_t = charged_energy_and_time(result.log)
    alns_imp = alns_it = alns_cand = None
    alns_beat = None
    val_s = None
    cert_n = None
    if controller_name in {"alns", "b1", "m1", "m1_no_reuse", "m1_full_eval"}:
        imp = it = cand = 0
        beat = False
        vs = 0.0
        cert = 0
        for d in result.decisions:
            audit = d.audit or {}
            alns = audit.get("alns") or {}
            imp += int(alns.get("improvements") or 0)
            it += int(alns.get("iterations") or 0)
            cand += int(alns.get("candidates_evaluated") or 0)
            beat = beat or bool(alns.get("improved_over_constructor"))
            vs += float(
                audit.get("validation_seconds_this_decision")
                if audit.get("validation_seconds_this_decision") is not None
                else audit.get("validation_seconds") or 0.0
            )
            if (
                audit.get("validation_status") == "CERTIFIED_FEASIBLE"
                or alns.get("feasibility_status") == "CERTIFIED_FEASIBLE"
            ):
                cert += 1
        alns_imp, alns_it, alns_cand, alns_beat = imp, it, cand, beat
        if controller_name in {"b1", "m1", "m1_no_reuse", "m1_full_eval"}:
            val_s = vs
            cert_n = cert
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
        executed_distance=exec_dist,
        charged_energy=ch_e,
        executed_charge_time=ch_t,
        planned_distance_sum_diagnostic=planned_sum,
        optimize_seconds=result.optimize_seconds,
        mean_decision_seconds=mean(opt_times) if opt_times else 0.0,
        no_feasible_continuation_count=result.no_feasible_continuation_count,
        replay_ok=report.ok,
        alns_improvements=alns_imp,
        alns_iterations=alns_it,
        alns_improved_over_constructor=alns_beat,
        alns_candidates=alns_cand,
        validation_seconds=val_s,
        certified_feasible_decisions=cert_n,
    )


def run_matched_case(
    case: BaselineCase,
    *,
    alns_iterations: int = 30,
    alns_time: float = 0.2,
    include_b1: bool = False,
    include_m1: bool = False,
) -> dict:
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
    out = {
        "case_id": case.case_id,
        "tags": list(case.tags),
        "insertion": asdict(_summarize(case, "insertion", ins_res)),
        "alns": asdict(_summarize(case, "alns", alns_res)),
    }
    if include_b1:
        from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc

        b1 = FullValidationAlnsMpc(
            case.instance,
            case.horizon,
            iterations=alns_iterations,
            time_limit_seconds=alns_time,
            seed=7,
        )
        b1_res = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=b1,
        )
        out["b1"] = asdict(_summarize(case, "b1", b1_res))
    if include_m1:
        from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
        from safe_time_evrp.commitment_safe_mpc.route_resource_profile import EvalMode

        for key, kwargs in (
            ("m1", {"eval_mode": EvalMode.INCREMENTAL_EVALUATION, "reuse_certificates": True}),
            ("m1_no_reuse", {"eval_mode": EvalMode.INCREMENTAL_EVALUATION, "reuse_certificates": False}),
            ("m1_full_eval", {"eval_mode": EvalMode.FULL_EVALUATION, "reuse_certificates": True}),
        ):
            ctrl = CertificateCarryingAlnsMpc(
                case.instance,
                case.horizon,
                iterations=alns_iterations,
                time_limit_seconds=alns_time,
                seed=7,
                **kwargs,
            )
            res = run_episode(
                case.instance,
                case.releases,
                fleet_size=case.fleet_size,
                horizon=case.horizon,
                max_replan_interval=case.max_replan_interval,
                t_max=case.t_max,
                controller=ctrl,
            )
            out[key] = asdict(_summarize(case, key, res))
    return out


def run_baseline_study(*, include_b1: bool = False, include_m1: bool = False) -> dict:
    rows = [run_matched_case(case, include_b1=include_b1, include_m1=include_m1) for case in build_baseline_suite()]
    alns_search = sum(1 for r in rows if (r["alns"].get("alns_iterations") or 0) > 0)
    alns_improve = sum(1 for r in rows if r["alns"].get("alns_improvements"))
    replay_ok = sum(1 for r in rows if r["insertion"]["replay_ok"] and r["alns"]["replay_ok"])
    summary = {
        "n_cases": len(rows),
        "both_replay_ok": replay_ok,
        "alns_cases_with_search_iterations": alns_search,
        "alns_cases_with_improvements": alns_improve,
        "metric_note": "executed_distance is physical depart arcs; planned_distance_sum_diagnostic is not operational.",
        "note": "ALNS need not dominate insertion on every case; search activity is required.",
    }
    if include_b1:
        summary["b1_replay_ok"] = sum(1 for r in rows if r.get("b1", {}).get("replay_ok"))
    if include_m1:
        summary["m1_replay_ok"] = sum(1 for r in rows if r.get("m1", {}).get("replay_ok"))
    return {"rows": rows, "summary": summary}


def write_baseline_artifacts(out_dir: Path, *, include_b1: bool = False, include_m1: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_baseline_study(include_b1=include_b1, include_m1=include_m1)
    if include_m1:
        name = "baseline_comparison_m1_ablation.json"
    elif include_b1:
        name = "baseline_comparison_b0_b1.json"
    else:
        name = "baseline_comparison.json"
    (out_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    import sys

    include_b1 = "--b1" in sys.argv
    include_m1 = "--m1" in sys.argv
    if include_m1:
        include_b1 = True
    art = write_baseline_artifacts(Path("docs/commitment_safe_mpc"), include_b1=include_b1, include_m1=include_m1)
    print(json.dumps(art["summary"], indent=2))
    for row in art["rows"]:
        a, b = row["insertion"], row["alns"]
        line = [
            row["case_id"],
            "ins_exec",
            round(a["executed_distance"], 2),
            "alns_exec",
            round(b["executed_distance"], 2),
            "completed",
            len(a["completed"]),
            len(b["completed"]),
            "iters",
            b.get("alns_iterations"),
            "imp",
            b.get("alns_improvements"),
            "replay",
            a["replay_ok"],
            b["replay_ok"],
        ]
        if include_b1 and "b1" in row:
            c = row["b1"]
            line.extend(
                [
                    "b1_exec",
                    round(c["executed_distance"], 2),
                    "b1_done",
                    len(c["completed"]),
                    "cert",
                    c.get("certified_feasible_decisions"),
                    "val_s",
                    round(c.get("validation_seconds") or 0.0, 4),
                    "b1_replay",
                    c["replay_ok"],
                ]
            )
        print(*line)
