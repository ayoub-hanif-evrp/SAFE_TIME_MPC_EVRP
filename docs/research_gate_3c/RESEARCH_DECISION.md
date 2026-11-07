# Research decision — Gate 3C

**Decision: NO-GO** (for the flexibility-terminal novelty claim)

Branch: `research/decision-mpc-gate`. Part 3 not started.

## Checklist vs GO criteria

| Criterion | Result |
| --- | --- |
| TW-feasible multi-vehicle EVRP-TW-D seeds at native Q | **Pass** (100% of probed Cus_5/Cus_15) |
| Amazon electrified sample validates under independent replay | **Pass** (modeled EV; travel-time distances) |
| Flexibility MPC changes present actions vs ordinary RH | **Partial** (Amazon 1/8; none on EVRP-TW-D) |
| Improves commitment-feasible service vs RH on held-out | **Fail** (tied on all pools) |
| Not identical to strong rollout | **Fail** (0% action divergence vs rollout) |
| No fake theorem / no OSM claim | **Pass** |

## What remains valuable

- Feasible multi-vehicle testbed + validator (replaces NN-only Gate 3B pilot).
- Honest Amazon electrification loader with travel-time matrices.
- Clear negative: a λ-weighted insertion-flexibility terminal on the same candidate set as PI rollout is **not** a new method in practice.

## What to stop doing

- Adding more datasets without a new mechanism.
- Claiming predictive flexibility value without beating rollout.

## If the project continues

Change the mathematical mechanism (e.g., different action space, information state, or commitment pricing), then re-run Gate 3C-style causal tests. Do not scale Part 3 on this terminal approx.

## Git / tests

Tip at decision commit: parent `9a3b5eb` plus this file. Local pytest includes Gate 3C testbed/MPC tests (67 total at last green run). Full EVRP-TW-D archive remains local (`GATE3C_DATA=1` for optional verify).
