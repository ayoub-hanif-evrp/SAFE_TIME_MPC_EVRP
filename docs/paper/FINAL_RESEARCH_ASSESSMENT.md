# Final research assessment

**Archived exploratory baseline SHA:** `442a42329d283bad14f1900eac6a37ab33b6e0cb`  
**Artifacts:** `docs/experiments/FINAL_COMPETITIVE_COMPARISON.json`,  
`FINITE_DEMAND_FORECAST_CALIBRATION.md`, `PREDICTIVE_OPPORTUNITY_AND_ACTION_AUDIT.md`

## What was fixed

1. **Demand model:** Finite population + active-period forecast replaces homogeneous Poisson over the full horizon. Development-segment calibration: predicted/realized ≈ **1.00** vs Poisson ≈ **9.31**.
2. **Windows:** Synthetic customers use train announcement-to-ready lead times and window spans (not `ready := announce`).
3. **Controller:** `BaselineAnchoredPredictiveCCE` keeps greedy-nominal CC-E as a validated incumbent and overrides only under a CRN causal margin.
4. **Compute:** Incumbent-first anytime path; candidate screening; cooperative budgets (not hard-preemptive ALNS).
5. **Accounting:** Cutoff vs natural completion remain distinct; AU status via `mark_finished`; certificates require independent verification.

## Empirical decision (held-out + development)

**Label:** `greedy_nominal_remains_strongest_empirical_contribution`

| Setting | Mean completed (dev, n=18) |
| --- | ---: |
| `cce_greedy_nominal` | **6.17** |
| `m1` | 4.89 |
| `b1` | 4.44 |
| `cce_finite_demand` | 4.17 |
| `bap_cce` | 3.56 |

- Development BAP − greedy-nominal completed Δ ≈ **−2.61** (better 1 / worse 8 / tie 9).
- Held-out final (6 test stems, fresh env XOR): BAP − greedy-nominal Δ ≈ **−2.17** (1 / 2 / 3).

**Recommendation:** Treat **greedy-nominal CC-E** as the project’s strongest empirical controller under the current Schneider-v2 protocol. Predictive superiority was **not** demonstrated.

## Opportunity vs model gap

Restricted offline hindsight improved on the greedy-nominal first action in **11/18** development epochs (rate ≈ 0.61). So the candidate set is not empty of predictive opportunity; the online finite-demand ranker / BAP override rule did not convert that offline opportunity into closed-loop gains.

## Limitations (explicit)

- Diagnostic/development stems include training instances; results are not a large confirmatory trial.
- Fresh environment seeds on Schneider bases do not create completely unseen static instances.
- Cooperative time limits are not hard real-time interrupts of ALNS.
- Greedy-nominal uses a different scoring formula than causal modes; it remains the empirical reference by closed-loop service, not by formula equivalence.

## Stopping rule

No further dataset switches, objective retuning, or test-set cycling. Further work, if any, should target converting the measured hindsight opportunity with better ranking under the **same** incumbent-anchored contract — or accept the nominal controller as the publishable empirical contribution.
