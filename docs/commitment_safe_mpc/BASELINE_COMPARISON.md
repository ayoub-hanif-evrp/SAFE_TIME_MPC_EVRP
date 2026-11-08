# Baseline comparison protocol

Status: **protocol defined; B0/B1/M1 not yet implemented on the unified plant.**

| ID | Controller | Role |
|----|------------|------|
| B0 | Reactive ALNS–MPC | Strong operational baseline (from `MPC_EVRP` ALNS via adapter) |
| B1 | Full-Validation Safe MPC | Same optimizer; every update fully commitment-validated (ablation) |
| M1 | Incremental Certificate-Carrying MPC | Proposed contribution |

## Fairness requirements

Same plant, visible information, fleet/battery constraints, acceptance rules, objective, compute budget, matched demand/disturbance realizations.

Never compare only against myopic or deliberately weak heuristics.
