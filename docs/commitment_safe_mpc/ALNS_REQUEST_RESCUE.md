# ALNS request-rescue neighborhood

**Controller:** `ReactiveAlnsMpc` in `alns_mpc.py`  
**Problem fixed:** destroy/repair previously operated only on customers already in the constructor’s served set, so \(S_{\mathrm{ALNS}} \subseteq S_0\).

## Request classification (within one `decide()`)

| Set | Meaning |
|-----|---------|
| Mandatory | Pending `observation.accepted` — must stay covered |
| Provisional assigned | Customers in current ALNS sequences |
| Rescue-eligible | `released_open` minus completed / in_service / **official** `observation.rejected` / horizon-deferred |
| Official rejected | Already in `observation.rejected` — never resurrected |
| Deferred | `ready > now + horizon` |

Constructor `plan.rejected` is **provisional**. Those IDs remain rescue-eligible until decision finalize.

## Response-deadline policy

`deadline(c) = node(c).window.due`. At the end of `decide()`: served → `newly_accepted`; horizon-deferred → `deferred`; otherwise unassigned open requests → `rejected`.

## Repair pool

`pool = removed ∪ rescue_eligible_unassigned`. Destroy may free provisional customers; if nothing is removable but the rescue pool is nonempty, repair still runs.

## Lexicographic objective

1. Commitment coverage (hard)  
2. Maximize `|served|`  
3. Minimize `(distance, charge_time)`  

Diagnostics: `rescued_customers`, `constructor_served`, `best_served`, `improved_coverage_over_constructor`.

## Regression

`tests/test_commitment_safe_rescue.py` — packing fixture where constructor serves `{A,B}` and ALNS recovers `{A,B,C}`.
