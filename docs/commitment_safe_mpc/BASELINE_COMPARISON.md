# Baseline comparison protocol

Status: **B0 hardened** and **B1 implemented** — insertion vs reactive ALNS–MPC vs full-validation ALNS–MPC on the authoritative plant.

| ID | Controller | Role |
|----|------------|------|
| Insertion | `EventTriggeredMPC` | Constructive baseline |
| B0 | `ReactiveAlnsMpc` | Strong reactive ALNS–MPC |
| B1 | `FullValidationAlnsMpc` | Same engine + explicit continuation witness |
| M1 | Incremental Certificate-Carrying MPC | Proposed contribution (**not implemented**) |

## Fairness requirements

Same plant, visible information (public snapshot), fleet/battery constraints, acceptance plant rules, matched demand realizations, matched ALNS budgets for B0/B1. Independent replay on all episodes. Operational metric: **executed distance** (not planned objective sum).

See `BASELINE_FAIRNESS_AUDIT.md`, `BASELINE_IMPLEMENTATION_RESULTS.md`, `B1_CORRECTNESS_RESULTS.md`.

## Commands

```bash
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --b1
```
