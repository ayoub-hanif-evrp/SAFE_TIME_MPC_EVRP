"""Development episode on one Schneider instance and an explicit release rule."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from safe_time_evrp import __version__
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.paths import project_root, schneider_dir
from safe_time_evrp.data.schneider import parse_schneider_file
from safe_time_evrp.evaluation.dynamic import indexed_stagger
from safe_time_evrp.evaluation.plotting import write_route_soc_plot
from safe_time_evrp.models.state import LogRecord
from safe_time_evrp.validation.replay import validate_log


def main() -> None:
    config_path = project_root() / "configs" / "development_scenario.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    instance_path = _find_instance(config["instance"])
    instance = parse_schneider_file(instance_path)
    scenario = indexed_stagger(instance, step=float(config["step"]), seed=int(config["seed"]))
    result = run_episode(
        instance,
        list(scenario.releases),
        fleet_size=int(config["fleet_size"]),
        horizon=float(config["horizon"]),
        max_replan_interval=float(config["max_replan_interval"]),
        t_max=instance.node(instance.depot_id).window.due,
    )
    report = validate_log(instance, result.log)
    if not report.ok:
        raise SystemExit(f"replay rejected the development episode: {report.code} {report.detail}")
    summary = {
        "announced": report.announced,
        "completed": report.completed,
        "rejected": report.rejected,
        "accepted_unfulfilled": report.accepted_unfulfilled,
        "open_requests": report.open_requests,
        "service_rate_on_announced": (len(report.completed) / len(report.announced) if report.announced else 0.0),
        "denominator": "announced_requests",
    }
    out = project_root() / "experiments" / "development" / config["instance"]
    out.mkdir(parents=True, exist_ok=True)
    decisions = [
        {
            "time": decision.time,
            "trigger": decision.trigger,
            "newly_accepted": decision.newly_accepted,
            "rejected": decision.rejected,
            "deferred": decision.deferred,
            "planned_service": decision.planned_service,
            "fallback_used": decision.fallback_used,
            "no_feasible_continuation": decision.no_feasible_continuation,
            "horizon_extended": decision.horizon_extended,
            "optimize_seconds": decision.optimize_seconds,
            "locked_destinations": decision.locked_destinations,
            "distance": decision.total_distance,
            "notes": decision.notes,
        }
        for decision in result.decisions
    ]
    (out / "service_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "decisions.json").write_text(json.dumps(decisions, indent=2), encoding="utf-8")
    (out / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(_record(item)) for item in result.log) + "\n",
        encoding="utf-8",
    )
    plot_status = write_route_soc_plot(instance, result.log, out / "route_soc.png")
    manifest = {
        "package_version": __version__,
        "config_sha256": sha256(config_path.read_bytes()).hexdigest(),
        "instance": instance.name,
        "instance_file": str(instance_path),
        "source_format": instance.source_format,
        "scenario": {
            "mechanism": scenario.mechanism,
            "version": scenario.version,
            "releases": scenario.releases,
        },
        "fleet_size": config["fleet_size"],
        "horizon": config["horizon"],
        "max_replan_interval": config["max_replan_interval"],
        "decision_count": len(result.decisions),
        "optimize_seconds": result.optimize_seconds,
        "simulation_seconds": result.simulation_seconds,
        "fallback_count": result.fallback_count,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "horizon_extended_count": result.horizon_extended_count,
        "replay_ok": report.ok,
        "vehicles_en_route_at_end": report.vehicles_en_route,
        "service_summary": summary,
        "plot": plot_status,
        "hard_timeout_guarantee": False,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "completed": summary["completed"], "decisions": len(decisions)}))


def _find_instance(name: str) -> Path:
    matches = list((schneider_dir() / "extracted").rglob(f"{name}.txt"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected one {name}.txt under the extracted Schneider archive, found {len(matches)}. "
            "Run python -m safe_time_evrp.data.download"
        )
    return matches[0]


def _record(record: LogRecord) -> dict:
    return {
        "time": record.time,
        "seq": record.seq,
        "kind": record.kind,
        "vehicle_id": record.vehicle_id,
        "data": record.data,
    }


if __name__ == "__main__":
    main()
