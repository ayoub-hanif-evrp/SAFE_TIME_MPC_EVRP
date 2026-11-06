"""Bounded Part 2 development pilot. Refuses to overwrite a completed manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from safe_time_evrp import __version__
from safe_time_evrp.data.paths import project_root
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.robust.baselines import run_nominal_mpc, run_reactive
from safe_time_evrp.robust.controller import SafeTimeController
from safe_time_evrp.robust.episode import run_robust_episode
from safe_time_evrp.robust.supervisor import SolverSupervisor
from safe_time_evrp.robust.triggers import TriggerPolicy
from safe_time_evrp.robust.uncertainty import RectangularUncertainty


def main() -> None:
    root = project_root()
    out = root / "experiments" / "development" / "part2_pilot"
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") == "completed":
            print(json.dumps({"skipped": True, "reason": "completed manifest exists", "path": str(manifest_path)}))
            return
    manifest = {
        "status": "running",
        "started": datetime.now(UTC).isoformat(),
        "version": __version__,
        "budget_note": "Development pilot only. No holdout and no superiority claim.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    instance = make_reference_instance("easy")
    uncertainty = RectangularUncertainty(1.0, 1.1, 1.0, 1.1, evidence="design_assumption")
    releases = [("C1", 0.0), ("C2", 5.0), ("C3", 10.0)]
    supervisor = SolverSupervisor()
    rows = []
    b1 = run_nominal_mpc(
        instance,
        releases,
        fleet_size=1,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
    )
    rows.append(
        {
            "policy": "b1_deterministic_mpc",
            "optimize_count": len(b1.decisions),
            "fallback_count": b1.fallback_count,
            "timeout_count": 0,
            "stale_count": 0,
            "commitment_failures": sum(status == "accepted_unfulfilled" for status in b1.final_requests.values()),
            "final_requests": b1.final_requests,
            "deadlines": [],
            "acceptance": "nominal insertion, not the rectangle",
        }
    )
    rows.append(
        {
            "policy": "b0_reactive_insertion",
            "final_requests": run_reactive(instance, releases, fleet_size=1, t_max=200),
            "acceptance": "nominal one-customer insertion",
        }
    )
    try:
        for policy, steps in (
            (TriggerPolicy.FIXED_PERIOD, 4),
            (TriggerPolicy.EVERY_EVENT, 4),
            (TriggerPolicy.SLACK_HEURISTIC, 4),
            (TriggerPolicy.VALIDITY_AWARE, 4),
        ):
            controller = SafeTimeController(
                instance,
                horizon=200,
                uncertainty=uncertainty,
                policy=policy,
                deadline=5.0,
                supervisor=supervisor,
                anytime_steps=steps,
                slack_time=1.0,
                slack_energy=0.5,
            )
            result = run_robust_episode(
                instance,
                releases,
                controller,
                fleet_size=1,
                t_max=200,
                replan_interval=40,
            )
            rows.append(
                {
                    "policy": policy.value,
                    "optimize_count": result.optimize_count,
                    "fallback_count": result.fallback_count,
                    "timeout_count": result.timeout_count,
                    "stale_count": result.stale_count,
                    "commitment_failures": result.commitment_failures,
                    "final_requests": result.final_requests,
                    "deadlines": [5.0],
                }
            )
    finally:
        supervisor.close()
    payload = {
        "status": "completed",
        "finished": datetime.now(UTC).isoformat(),
        "instance": instance.name,
        "uncertainty": {
            "time": [uncertainty.time_lower, uncertainty.time_upper],
            "energy": [uncertainty.energy_lower, uncertainty.energy_upper],
            "evidence": uncertainty.evidence,
        },
        "rows": rows,
        "interpretation": ("Counts are one deterministic development run. They are not a statistical comparison."),
    }
    (out / "pilot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(out / "pilot.json"), "rows": rows}))


if __name__ == "__main__":
    main()
