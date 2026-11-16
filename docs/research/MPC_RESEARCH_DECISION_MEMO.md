# Research decision memo — Commitment-Safe Stochastic MPC

**Date:** 2026-11-16  
**Base SHA before this wave:** `44272e6`  
**Hypothesis:** Stochastic commitment-safe MPC improves expected realized economic value vs strongest MPC baseline while preserving stated commitment conditions and meeting a practical compute budget.

## Plain answers

| Question | Answer |
|---|---|
| What MPC mechanism was improved? | (1) Scenario-terminal honesty (cache + selection classes). (2) Energy-gated anticipatory charging from diagnosis of charge-vs-serve failures. |
| What new mathematical property was established? | Scenario-terminal honesty proposition + certified-emission soundness. **Not** recursive feasibility. |
| Why does it matter for electric routing? | Prevents false stochastic terminal claims; gates anticipatory charge by opportunity cost vs service. |
| Benefit over strongest baseline? | Stem-clustered Δ vs GN ≈ **+145** econ (tally **7/2**), but 95% CI **[−279, +570]** includes 0. Mean completed still trails GN (3.89 vs 4.28). Energy-gate ablation: gated CSS **worse** mean econ than ungated (−27 vs +117). Existing stochastic CCE mean econ **+215** exceeds CSS on this run. |
| Statistically / operationally credible? | **No** — CI includes 0; heavy tails; ungated ablation outperforms gated method on mean. |
| Computational constraints? | Decision p99 still ≫ 0.35s; overruns remain material (~101 on CSS). Cooperative only. |
| Sufficient for top-tier paper? | **No.** |

## Gates

| Gate | Result |
|---|---|
| A Validity | **Pass** for scenario-terminal honesty + no hidden future in online path |
| B Mechanism | **Partial** — diagnosis causal; energy gate did not reliably improve vs its ablation |
| C Performance | **Fail** — no reliable clustered economic superiority vs GN |
| D Computation | **Fail** — overruns / p99 outside practical hard real-time |
| E Novelty | **Insufficient** — warm-start/validation + charge gate not yet a distinctive proved MPC advance with strong evidence |

## Remaining scientific obstacles

1. No proved forward-invariant commitment set (RF withdrawn).
2. Forecast still not shown to create reliable economic value.
3. Energy-gated charge fixed a diagnosed failure mode on some stems but degraded average service/econ vs ungated CSS.
4. Stochastic CCE can outperform the proposed controller on the same development cells — undermines “proposed method” superiority.
5. Compute–performance frontier not yet acceptable under 0.35s cooperative wall.

## Decision

**Do not proceed to confirmatory / test-set evaluation.**  
Preserve negative findings. Next scientific work must identify a mechanism that beats both GN and ungated CSS with clustered uncertainty excluding zero — or conclude the hypothesis is unsupported under this regime.
