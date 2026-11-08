# Revalidation cost profile (instrumentation for future M1)

**Purpose:** measure redundant full-validation work under B1 — **no M1 algorithm**.  
Artifact: `revalidation_cost_profile.json` (suite run with `FullValidationAlnsMpc`).

## What is logged per decision

- Routes / segments revalidated  
- Charge visits checked  
- Obligations (pending accepted ∪ proposed new) rechecked  
- Validation milliseconds (aggregated)  
- Whether the previous witness remained feasible after revalidation  

## Suite snapshot

| Case | Decisions | Routes revalidated | Obligations rechecked | Prev still feasible | Prev invalidated | Validation s |
|------|-----------|--------------------|-----------------------|---------------------|------------------|--------------|
| B_phase_b | 11 | 42 | 10 | 8 | 2 | ~0.00017 |
| B_easy_dynamic | 12 | 46 | 13 | 8 | 3 | ~0.00021 |
| B_tight_battery | 9 | 34 | 8 | 6 | 2 | ~0.00014 |
| B_competing | 18 | 70 | 28 | 13 | 4 | ~0.00034 |
| B_adversarial_overaccept | 11 | 21 | 20 | 8 | 2 | ~0.00016 |

## Redundant work identified (M1 target)

1. **Unchanged obligations rechecked every epoch** even when anchors and the locked prefix did not change.  
2. **Full fleet re-evaluation** of every vehicle route, including idle / empty suffixes.  
3. **Repeated charge feasibility** on the same charge visit when only a distant vehicle’s open requests changed.  
4. **Previous witness often still feasible** (majority of epochs) yet B1 still re-runs complete `evaluate_route` before reuse — correct for B1, wasteful for a certificate-carrying M1.  
5. **Double validation** when a new-accept proposal fails: B1 validates with new accepts, then again without them.

These are the quantitative hooks M1 should attack (incremental certificates / delta validation). Do not interpret current millisecond totals as evidence that full validation is cheap at paper-scale instances.
