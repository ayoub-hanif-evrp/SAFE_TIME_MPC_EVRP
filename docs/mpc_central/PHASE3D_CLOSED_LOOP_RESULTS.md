# Phase 3D — Closed-loop development pilot

**Verdict: REVISE**

Artifacts: [`phase3d_results.json`](phase3d_results.json), [`phase3d_au_residual.json`](phase3d_au_residual.json)

## What was run

1. **Repaired fork values** — Cases A/B/C under B1-validated recourse + arc-table distance.  
2. **Fairness suite** — budgets `(3, 4)`, order/scenario stress (18 comparisons).  
3. **Head-to-head** — adaptive vs uniform / equal allocation / paired CRN.  
4. **Closed-loop pilot** on **development** cases only, with forecast fitted on **train** only:
   - reactive insertion  
   - B1  
   - M1  
   - `CommitmentSafePredictiveMpc` with **causal scenario rollouts** (uniform / paired-CRN indices)  
5. **Holdout** (`B_adversarial_overaccept`) listed and left unevaluated.  
6. **Full AU residual audit** on all 31 frontier AU source rows.

## Fairness (reconciled)

| Metric | Value |
|--------|------:|
| Comparisons | 18 |
| Adaptive better than uniform | 3 |
| Ties | 15 |
| Fragile notes | 3 (budget-3 wins vanish under reversed candidate order) |

## Closed-loop outcomes

On both development cases, predictive MPC with causal rollouts remains **indistinguishable from B1** on completed customers and accepted-unfulfilled counts (REVISE — no manufactured win). Decisions carry `causal_rollouts=1`.

## AU residual audit

| Metric | Value |
|--------|------:|
| Source AU rows / audited | 31 / 31 |
| Cutoff + AU reproduced | 21 |
| Non-reproduction (no AU on re-run) | 10 |
| Cutoff + feasible residual continuation | **0** |
| Cutoff + infeasible/unknown residual | 21 |

## Scientific decision

**REVISE** — Evaluation contracts and a plant-facing predictive MPC with causal rollouts are in place, but there is not yet a defensible mechanism-specific closed-loop improvement over strong reactive B1 / established rollout baselines. Adaptive allocation remains order-fragile.

### Supported

- Nonzero executed-distance scoring  
- B1-validated scenario recourse  
- Non-renormalizing partial-sample expectation  
- Causal closed-loop scenario rollouts inside `CommitmentSafePredictiveMpc`  
- Train-only forecasts; holdout untouched  
- AU residual probes distinguishing cutoff from residual feasibility (here: residual failed on all reproduced AU cutoffs)  

### Unproved

- Order-robust allocation advantage  
- Predictive MPC superiority vs B1 / equal / CRN  
- Holdout generalization  
- Global multistage optimality of the offline first-action reference  
