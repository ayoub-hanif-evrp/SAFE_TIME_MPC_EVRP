# Part 2.5 development results

**Not a holdout. Not a claim of statistical superiority.**

## Design

- Parents: `c101C5`, `r104C5`, `rc105C5` (distinct Schneider C5 geometries that exist on disk).
- Releases: indexed stagger, step 40.
- Fleet size 2; horizon = depot due date; replan interval 200.
- Uncertainty / disturbance rectangle: time and energy factors in `[0.95, 1.05]` (design assumption).
- Disturbance modes: `nominal`, `upper`, `lower`, `mixed` (deterministic seeds).
- Decision deadline for robust policies: 1.0 s (measured wall clock with process isolation).
- Policies: Part 1 deterministic MPC (nominal plant only); fixed-period robust; every-event robust (anytime insertion + certified backup); validity-aware robust.
- Manifest: `experiments/development/part2_5_study/manifest.json` (gitignored). Refuses overwrite when `status=completed`.

## Aggregate counts (39 rows)

| Policy | Disturbance | Served / announced | Mean optimize count | Fallbacks | Stale | Timeouts | Replay ok |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 deterministic MPC | none | 0.600 | 18.7 | 0 | 0 | 0 | n/a in this table |
| fixed_period | all four | 0.533 | 5.7 | 3 total | 0 | 0 | yes |
| every_event | all four | 0.533 | 16.3 | 2 total | 0 | 0 | yes |
| validity_aware | all four | 0.533 | 5.0 | 0 | 0 | 0 | yes |

Commitment failures across all robust rows: **0**.  
False certificate flags recorded: **0**.  
Deadline overruns (timeout_count): **0** at the 1 s budget on these C5 instances.

## Interpretation

- Validity-aware used fewer optimizations than every-event on the same certificate and plant (5.0 vs 16.3 mean) with the same aggregate serve rate on this tiny set.
- That matches Proposition 5 (skip optional solves while the backup remains valid). It does **not** show better service.
- Deterministic MPC on the nominal plant served a slightly higher fraction here (0.600 vs 0.533). Robust policies are more selective; this is one small development sample, not a ranking.
- Upper / lower / mixed disturbances inside the rectangle did not produce commitment failures or replay failures after the rejection/service status repair.

## Negative findings

- No evidence that the proposed trigger improves service under a matched compute budget.
- No new theorem is demonstrated by these numbers.
- Process startup can still dominate sub-second budgets on larger instances; 1 s was adequate here.
