# Phase 3F — Decision experiments

Artifact: [`phase3f_results.json`](phase3f_results.json)

## Task 1 — Admission semantics

Reproduced `A_low_soc_charge` seed 7 mid-service state at \(t\approx 28.38\) with `in_service=["C1"]`. After repair: no illegal eligible admits, no `newly_accepted` containing C1, no second-vehicle service leg to C1. **Pass.**

## Task 5 — Restricted decision oracle (Case-A charge fork)

| Rule | Action |
|------|--------|
| Exact restricted mean (enumerated) | `charge_first` (mean ≈ 122.3) |
| B1 / serve reference | serve Near |
| Paired \(\mathbb{E}[\Delta]\) charge vs serve | ≈ +34.3 |
| Paired \(\min\Delta\) | ≈ −9.7 → **fails** `RISK_FLOOR=0` |
| Switching decision | stay with serve / B1 |
| Captures nonmyopic charge? | **No** |

Disclaimer: restricted finite-horizon enumeration only — not a global EVRP optimum.

## Task 6 — Matched development evaluation

Cases × seeds: `A_dense_arrivals`, `A_low_soc_charge`, `B_easy_dynamic` × `{3,7,11}` (predeclared; not selected by win rate).

Controllers: B1, M1, identical-candidate stochastic rollout, switching MPC, no-forecast switching, no-switching ablation.

| Metric | Value |
|--------|------:|
| Valid cells | 9 / 9 |
| Wins vs B1 | 0 |
| Losses vs B1 | 0 |
| Equals B1 (completed/AU/distance) | 6 |
| Equals stochastic | 6 |
| Total recorded switches | 5 (all on `B_easy_dynamic`) |

Switches on `B_easy_dynamic` change route geometry / timing but not completed counts (still 3). Dense / low-SOC cells default to B1 and match B1 service outcomes after persistent-B1 matching.

## Gate

**`REVISE`**

- Admission repair is valid.
- Switching rule is algorithmically distinct from unguarded rollout.
- It makes some switches, but does not improve service vs B1 on the gate cells.
- Oracle shows the risk floor blocks the nonmyopic charge action.
- Viability metrics show a signal but are not yet an operational differentiator with empirical gains.

**Not `GO_PROTOTYPE`:** no credible development win package.  
**Not `NO-GO`:** the method is not merely a renamed rollout; plant-valid scaffolding and paired B1 interface remain useful.

## Smallest next scientific choice

Either (i) redesign the EVRP-specific viability gate so it can authorize the oracle charge action without seed-tuned thresholds, or (ii) pivot the central claim away from closed-loop predictive superiority toward commitment certificates / viability analysis as the contribution — with experiments built for that claim. Do **not** launch a broad campaign until that choice is explicit.
