# Research decision memo — Commitment-Safe Stochastic MPC

**Date:** 2026-11-17  
**Completion SHA (pending commit):** scientific completion artifacts on top of `5f32372`  
**Hypothesis:** Stochastic commitment-safe MPC improves expected realized economic value vs strongest MPC baseline while preserving stated commitment conditions and meeting a practical compute budget.

## Plain answers

| Question | Answer |
|---|---|
| What MPC mechanism was improved? | Scenario-terminal honesty; energy-gated anticipatory charging from divergence diagnosis. |
| What new mathematical property? | Scenario-terminal honesty + certified-emission soundness. **Not** recursive feasibility. |
| Why EV-specific? | Charge gated by opportunity cost vs service; regimes vary battery/chargers/charge rate. |
| Benefit vs strongest baseline? | Development clustered CI vs GN still includes 0. EV factorial: CSS better **17/54**, worse **35/54**. |
| Credible? | **No.** |
| Compute OK? | **No** — small instances often cooperative; 100-customer p50≈3s, >93% over 0.70s. |
| Top-tier evidence? | **No.** |

## Completed remaining gaps

### Divergence reconstruction
Worst stems reconstructed at first CSS≠GN decision with observation (accepted, SoC), candidate diagnosis, and labels:
- `rc108C10` / `rc108C15`: ranking / accept-set; GN matches hindsight; CSS idle or charge vs GN service.
- `r103C10`: later accept-set divergence with existing commitments; feasibility empty-set under hindsight scoring.
- `c106C15`: both accept C1; CSS wins episode but hindsight prefers GN-like continuation structure.

### EV regime factorial (54/54 cells, 0 failures)
Predeclared stems × {low,medium,high} × {tight/nominal/generous/infinite battery, sparse chargers, slow charge}.
- Mean Δ by regime: tight battery ≈+47; sparse chargers ≈+74; nominal ≈−355; infinite ≈−1482.
- **No systematic EV-advantage story:** relaxing energy often *hurts* CSS relative to GN on these cells.

### Budget frontier
Prespecified budgets {0.15, 0.35, 0.70, 1.50}. More wall time is **not** monotone-improving (e.g. `c106C15` collapses at ≥0.70 with many certificate losses).

### Large-instance probe (100 customers)
`c101_21`, `r101_21`, `rc101_21`: replay OK; CSS economic Δ large positive on 2/3, negative on `rc101_21`. Decision p50≈3s, frac_over_0.70≈0.94 — **not** a practical real-time MPC regime.

## Gates

| Gate | Result |
|---|---|
| A Validity | **Pass** (scenario-terminal honesty) |
| B Mechanism | **Partial** (diagnosis causal; regime evidence mixed/negative for EV claim) |
| C Performance | **Fail** |
| D Computation | **Fail** |
| E Novelty | **Fail** for top-tier bar |

## Decision

**Do not proceed to confirmatory / test-set evaluation.**  
Remaining obstacle: no mechanism that reliably beats GN across regimes with clustered uncertainty excluding 0 and practical decision latency.
