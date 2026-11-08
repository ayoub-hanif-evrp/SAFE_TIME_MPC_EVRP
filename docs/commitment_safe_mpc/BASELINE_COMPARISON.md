# Baseline comparison protocol

Status: **B0 implemented** — insertion MPC vs reactive ALNS–MPC on the authoritative plant.

| ID | Controller | Role |
|----|------------|------|
| Insertion | `EventTriggeredMPC` | Constructive baseline |
| B0 | `ReactiveAlnsMpc` | Strong reactive ALNS–MPC |
| B1 | Full-Validation Safe MPC | **Next** — same engine + explicit continuation witness |
| M1 | Incremental Certificate-Carrying MPC | Proposed contribution (after B1) |

## Fairness requirements

Same plant, visible information (public snapshot), fleet/battery constraints, acceptance plant rules, matched demand realizations. Independent replay on all episodes.

See `BASELINE_FAIRNESS_AUDIT.md` and `BASELINE_IMPLEMENTATION_RESULTS.md`.
