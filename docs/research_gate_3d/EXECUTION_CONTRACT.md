# Gate 3D — Execution contract

Scientific closed-loop comparisons for dynamic EVRP-MPC run only through
[`FleetSimulator`](../../src/safe_time_evrp/environment/simulator.py) via
[`mpc3c/sim_experiment.py`](../../src/safe_time_evrp/mpc3c/sim_experiment.py).

## Required plant behavior

| Rule | Gate 3C bug | Gate 3D contract |
| --- | --- | --- |
| Multi-stop tours | `evaluate_route([first])` auto-appends depot return → microtrips | Dispatch **full** suffixes; first action may travel to a customer while remaining suffix is retained |
| Noninterruptibility | Custom loop could “cancel” mid-action by rebuilding state | Locked travel/service/charge continue; replan updates suffix only |
| Time advance | `time = max(vehicle end times)` desync | Event-queue clock; idle/replan anchors equal `simulator.time` |
| Replay | Not required on custom loop | Logged episodes must pass [`validation/replay.py`](../../src/safe_time_evrp/validation/replay.py) |
| Accept/reject | Implicit | Accept only plant-released customers appearing in cleaned routes; do not reject customers before their windows open |

## Tests

[`tests/test_gate3d_execution_contract.py`](../../tests/test_gate3d_execution_contract.py) encodes the above. Gate 3C `run_dynamic` is retired as an alias of `run_sim_dynamic`.

## Controllers in scope

Myopic, ordinary RH open-loop, strong PI/stochastic rollout, flexibility MPC (info-corrected). **No new mechanism** in this gate.
