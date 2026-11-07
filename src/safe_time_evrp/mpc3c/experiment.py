"""Matched dynamic experiments — Gate 3C API retained, Gate 3D harness used.

``run_dynamic`` is retired for scientific comparisons. Callers of
``compare_controllers`` are routed through the simulator-backed runner.
"""

from __future__ import annotations

from safe_time_evrp.mpc3c.sim_experiment import RunResult, StepLog, compare_controllers, run_sim_dynamic

# Backward-compatible alias: old name now means the simulator-backed runner.
run_dynamic = run_sim_dynamic

__all__ = [
    "RunResult",
    "StepLog",
    "compare_controllers",
    "run_dynamic",
    "run_sim_dynamic",
]
