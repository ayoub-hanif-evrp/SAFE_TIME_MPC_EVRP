"""Modest Part 2.5 development study. Not a holdout and not a superiority claim."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from safe_time_evrp import __version__
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.paths import project_root
from safe_time_evrp.data.schneider import parse_schneider_file
from safe_time_evrp.environment.disturbance import ArcDisturbanceSampler
from safe_time_evrp.evaluation.dynamic import indexed_stagger
from safe_time_evrp.robust.controller import SafeTimeController
from safe_time_evrp.robust.episode import run_robust_episode
from safe_time_evrp.robust.supervisor import SolverSupervisor
from safe_time_evrp.robust.triggers import TriggerPolicy
from safe_time_evrp.robust.uncertainty import RectangularUncertainty
from safe_time_evrp.validation.replay import validate_log

# Distinct small Schneider parents. Not a holdout set.
_PARENTS = ("c101C5", "r104C5", "rc105C5")
_DEADLINE = 1.0
_FACTORS = (0.95, 1.05)


def _releases(instance, step: float = 40.0):
    return list(indexed_stagger(instance, step=step).releases)


def stable_seed(*parts: str, modulus: int = 10_000) -> int:
    """Policy-independent deterministic seed. Do not use process-randomized hash()."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulus


def _service_rate(final_requests: dict[str, str]) -> dict[str, float]:
    announced = len(final_requests)
    completed = sum(1 for status in final_requests.values() if status == "completed")
    accepted = sum(
        1
        for status in final_requests.values()
        if status in {"completed", "accepted", "accepted_unfulfilled", "in_service"}
    )
    failures = sum(1 for status in final_requests.values() if status == "accepted_unfulfilled")
    return {
        "announced": announced,
        "completed": completed,
        "served_of_announced": completed / announced if announced else 0.0,
        "accepted": accepted,
        "commitment_failures": failures,
    }


def main() -> None:
    root = project_root()
    out = root / "experiments" / "development" / "part2_5_study"
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") == "completed":
            print(json.dumps({"skipped": True, "path": str(manifest_path)}))
            return
    manifest_path.write_text(
        json.dumps({"status": "running", "started": datetime.now(UTC).isoformat(), "version": __version__}, indent=2),
        encoding="utf-8",
    )
    extracted = root / "data" / "raw" / "schneider_evrptw" / "extracted" / "evrptw_instances"
    uncertainty = RectangularUncertainty(_FACTORS[0], _FACTORS[1], _FACTORS[0], _FACTORS[1])
    rows = []
    supervisor = SolverSupervisor()
    try:
        for parent in _PARENTS:
            path = extracted / f"{parent}.txt"
            if not path.exists():
                rows.append({"parent": parent, "error": "missing_instance"})
                continue
            instance = parse_schneider_file(path)
            releases = _releases(instance)
            horizon = instance.node(instance.depot_id).window.due
            # Deterministic MPC on nominal plant.
            nominal = run_episode(
                instance,
                releases,
                fleet_size=2,
                horizon=horizon,
                max_replan_interval=200,
                t_max=horizon,
            )
            rows.append(
                {
                    "parent": parent,
                    "policy": "b1_deterministic_mpc_nominal",
                    "disturbance": "none",
                    **_service_rate(nominal.final_requests),
                    "fallback_count": nominal.fallback_count,
                    "optimize_count": len(nominal.decisions),
                    "stale_count": 0,
                    "timeout_count": 0,
                    "deadline": None,
                }
            )
            for mode in ("nominal", "upper", "lower", "mixed"):
                for policy in (
                    TriggerPolicy.FIXED_PERIOD,
                    TriggerPolicy.EVERY_EVENT,
                    TriggerPolicy.VALIDITY_AWARE,
                ):
                    disturbance = ArcDisturbanceSampler(
                        _FACTORS[0],
                        _FACTORS[1],
                        _FACTORS[0],
                        _FACTORS[1],
                        seed=stable_seed(parent, mode),
                        mode=mode,
                    )
                    controller = SafeTimeController(
                        instance,
                        horizon,
                        uncertainty,
                        policy,
                        _DEADLINE,
                        supervisor,
                        anytime_steps=6,
                    )
                    result = run_robust_episode(
                        instance,
                        releases,
                        controller,
                        fleet_size=2,
                        t_max=horizon,
                        replan_interval=200,
                        disturbance=disturbance,
                    )
                    replay = validate_log(instance, result.log)
                    rows.append(
                        {
                            "parent": parent,
                            "policy": policy.value,
                            "disturbance": mode,
                            **_service_rate(result.final_requests),
                            "fallback_count": result.fallback_count,
                            "optimize_count": result.optimize_count,
                            "stale_count": result.stale_count,
                            "timeout_count": result.timeout_count,
                            "deadline": _DEADLINE,
                            "replay_ok": replay.ok,
                            "replay_code": replay.code,
                            # Exact false-feasible measurement requires the Gate 3A oracle.
                            "false_certificate": None,
                            "false_certificate_note": "not_applicable_without_exact_oracle",
                        }
                    )
    finally:
        supervisor.close()
    payload = {
        "status": "completed",
        "finished": datetime.now(UTC).isoformat(),
        "version": __version__,
        "budget_note": "Development study under a few Schneider C5 parents. No holdout. No superiority claim.",
        "uncertainty": {"time": list(_FACTORS), "energy": list(_FACTORS), "evidence": "design_assumption"},
        "deadline_seconds": _DEADLINE,
        "rows": rows,
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(out / "results.json"), "rows": len(rows)}))


if __name__ == "__main__":
    main()
