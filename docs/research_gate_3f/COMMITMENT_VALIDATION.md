# Gate 3F — Commitment validation

## Nominal admission gate

`_routes_cover_commitments` requires:

1. No duplicate service assignments across vehicles.
2. Nominal `evaluate_route` feasible for each vehicle suffix.
3. All pending accepted customers covered by served sets.

## Budgeted robust check

`robust_routes_cover_commitments(..., energy_scale, time_scale)` re-evaluates under scaled energy and travel times. This is an **explicit budget**, not an adversary and not a recursive-feasibility theorem.

## Real-time causality

With `advance_plant_during_optimize=True`, if a plant event falls inside the optimize interval the candidate is discarded (stale) and not applied. Locked noninterruptible actions continue. Hard real-time / preemption guarantees are **not** claimed beyond this contract.

## Interpretation

“Zero commitment violations” in diagnostics is empirical under the stated model and gate — not a proof of robust recursive feasibility.
