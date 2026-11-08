# Incremental route-resource certificates

Module: `route_resource_profile.py`

## Modes

| Mode | Behavior |
|------|----------|
| `FULL_EVALUATION` | Always `evaluate_route` from the vehicle anchor |
| `INCREMENTAL_EVALUATION` | Reuse an exact matching visit prefix / anchor; recompute the affected suffix; fall back to full on uncertainty |

Approximate prechecks never certify feasibility. Uncertain → full evaluation.

## Soundness target

For supported states/plans with a valid certificate version:

`VALID_INCREMENTAL(state, plan, certificate) ⇔ VALID_FULL(state, plan)`

on feasibility, served set, distance, charge time, depot return, and commitment coverage.

Equivalence regressions: `tests/test_commitment_safe_m1.py`.

## Work bound

In the worst case, suffix recomputation is still O(route length). No O(1)/O(log n) claim.
