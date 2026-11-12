# Phase 3D — Closed-loop development pilot

**Verdict: REVISE**

Artifact: [`phase3d_results.json`](phase3d_results.json)

## What was run

1. **Repaired fork values** — Cases A/B/C under B1-validated recourse + arc-table distance.  
2. **Fairness suite** — budgets `(3, 4)`, order/scenario stress (18 comparisons).  
3. **Head-to-head** — adaptive vs uniform / equal allocation / paired CRN on base order.  
4. **Closed-loop pilot** — `B_phase_b`, `B_easy_dynamic` under matched seeds/budgets:
   - reactive insertion  
   - B1 (`FullValidationAlnsMpc`)  
   - M1 (`CertificateCarryingAlnsMpc`)  
   - `CommitmentSafePredictiveMpc` (uniform forecast allocation)  
   - predictive + paired-CRN scenario indices  

Holdout untouched. No large frontier benchmark.

## Fairness (reconciled with JSON)

| Metric | Value |
|--------|------:|
| Comparisons | 18 |
| Adaptive better than uniform | 3 |
| Uniform better | 0 |
| Ties | 15 |
| Fragile notes | 3 (budget-3 wins vanish under reversed candidate order) |

Adaptive also records some base-order wins vs equal allocation; those inherit the same order fragility. Classic OCBA was **not** used (deterministic scenario values).

## Closed-loop outcomes

On both development cases, predictive MPC was **indistinguishable from B1** on completed customers and accepted-unfulfilled counts. All replay validations passed in the pilot artifact. Predictive wall-clock optimize time was small (~0.03 s mean) under the cooperative deadline.

## Scientific decision

**REVISE** — Evaluation contracts are repaired and a plant-facing predictive MPC exists, but there is not yet a defensible, mechanism-specific closed-loop improvement over strong reactive B1 / established rollout baselines. Do not claim novelty from the adaptive top-two sampler.

### Supported

- Nonzero executed-distance scoring from arc tables  
- B1-validated scenario recourse (insertion labeled separately)  
- Non-renormalizing partial-sample expectation  
- Live `CommitmentSafePredictiveMpc` on `FleetSimulator` / `run_episode`  
- Phase 3C order-fragility retained as negative evidence  

### Unproved

- Order-robust allocation advantage  
- Predictive MPC superiority vs B1 / equal / CRN  
- Train→holdout forecast value  
- Global multistage optimality of the offline first-action reference  

## Next (only if funded)

Strengthen forecast-driven candidate *generation* (not only scoring), add true plant-fork scenario rollouts if/when simulator cloning is available, and re-run a slightly larger development pilot before any holdout.
