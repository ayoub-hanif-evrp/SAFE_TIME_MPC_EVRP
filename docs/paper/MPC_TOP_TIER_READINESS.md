# Top-tier readiness — Commitment-Safe Stochastic MPC

**Verdict:** `not_ready` — development gate FAIL; research hypothesis unsupported under current evidence.

**Protocol:** `mpc_corrected_development_v1` + scenario-terminal honesty + energy-gated charge  
**Stopping rule:** no confirmatory campaign.

## Gates (research)

| Gate | Status |
|---|---|
| A Validity (scenario-terminal honesty, no future leak) | **PASS** |
| B Mechanism (causal, reproducible) | **PARTIAL** |
| C Performance vs greedy-nominal (clustered CI) | **FAIL** |
| D Computation (0.35s regime) | **FAIL** |
| E Novelty sufficient for top-tier | **FAIL** |

## Latest development snapshot (9 stems × 2)

| Controller | Completed | AU | Economic | Decide p50/p99 | Overruns | Loss events |
|---|---:|---:|---:|---:|---:|---:|
| Greedy-nominal | 4.28 | 1.61 | −172 | 0.009 / 0.56 | 30 | 0 |
| Stochastic CCE | 5.28 | 0.50 | **215** | 0.063 / 0.81 | 243 | 0 |
| CSS (energy-gated) | 3.89 | 1.00 | −27 | 0.077 / 0.73 | 101 | 154 |
| CSS no energy gate | 4.28 | 0.44 | 117 | 0.061 / 0.86 | 116 | 103 |

CSS vs GN clustered economic: Δ≈+145, tally 7/2, 95% CI **[−279, +570]** (includes 0).

## Deliverables

1. `docs/research/MPC_DECISION_QUALITY_DIAGNOSIS.md` — A–F decomposition  
2. `docs/research/MPC_FORMAL_CONTRIBUTION.md` — formulation + valid propositions  
3. `docs/research/MPC_EV_MECHANISM_STUDY.md` — energy-gated charge  
4. `docs/experiments/MPC_CORRECTED_DEVELOPMENT_RESULTS.*` — comparison  
5. `docs/research/MPC_RESEARCH_DECISION_MEMO.md` — go/no-go  

See also `MPC_CERTIFICATE_LOSS_SCIENCE.md`.

## Bottom line

Validity defects in scenario-terminal caching/selection were corrected. A diagnosis-driven EV charge gate was implemented. **Credible superiority for a top-tier MPC paper is not demonstrated.**
