# Accelerated development results

**Verdict: NO-GO**

Artifact: [`accelerated_results.json`](accelerated_results.json)

## Design

Preregistered development matrix (holdout untouched):

- `B_phase_b`, `B_tight_battery`, `B_easy_dynamic`  
- `A_low_soc_charge`, `A_dense_arrivals`, `A_tight_windows`  

Forecast: train atoms + **preregistered** announcement μ=12 (not pooled ready gaps).

Controllers (matched plant releases):

1. Reactive B1  
2. M1  
3. Standard stochastic MPC (`stochastic_uniform`) — same counterfactual candidates + forecast  
4. Proposed MPC (`proposed_mpc`) — same candidates, paired-CRN label  
5. No-forecast ablation  

## Headline numbers

| Metric | Value |
|--------|------:|
| Cases | 6 |
| Diversity gate pass | 6/6 |
| Proposed wins vs B1 (completed↑, AU not↑) | **0** |
| Proposed losses vs B1 | **6** |
| Proposed wins vs identical-candidate stochastic | **0** |
| Mean opt seconds (proposed / B1) | ~0.065 / ~0.129 |

Paired completed gaps vs B1 were negative on every case (e.g. −2 to −7 customers). Replay mostly ok; one case flagged not-all-replay-ok.

## Interpretation

1. **Validity work succeeded enough to trust a negative result.**  
2. **Action diversity exists**, but the predictive scorer does not choose better physical policies than B1.  
3. **Proposed ≡ stochastic rollout** under identical candidates → no novel selection theorem demonstrated.  
4. Do **not** scale holdouts or claim top-tier novelty from this mechanism.

## Formal difference vs ordinary stochastic rollout

With the same candidate set and forecast model, the live “proposed” controller is an ordinary stochastic rollout argmax (allocation label differs). Any paper claim must therefore rest on **commitment-preserving counterfactual construction + evaluation contracts**, and must show those change outcomes — which this pilot does not.

## Next scientific move (smallest)

Instrument epochs where the chosen first leg differs from B1’s first leg; if MPC prefers wait/reject/charge, check whether residual terminal scoring or short-horizon bias is responsible. Fix scoring before expanding cases.
