# Urgent correctness repair (post-`b3c709f` audit)

**Branch:** `research/decision-relevant-dual-mpc`  
**Trigger:** Independent audit of commit `b3c709fb760eabddcb3f3b841c76dd8fae497458`  
**Goal:** Make the dynamic EVRP–MPC model, oracle claims, and bound certificates describe the *same* problem before any pruning/scalability claim.

## Executive verdict

| Claim before repair | Status after repair |
|---------------------|---------------------|
| Generic TEI bound is a valid UB for dynamic announcements | **Withdrawn** (`UNSUPPORTED_BOUND` / QUARANTINED) |
| `EXACT_OPTIMUM` = general dynamic EVRP optimum | **Relabeled** → `EXACT_OPTIMUM_RESTRICTED` (continuation caps) |
| ACCEPT only at customer node | **Fixed** → fleet-level ACCEPT after announcement |
| Closed-loop ends when accepted set done | **Fixed** → `episode_complete` awaits future releases + depot |
| Frozen 8-instance suite (all value 9.75) is a scale study | **Retired for behavior** → discriminating suite D1–D4 |
| Generic prune saves compute | **Still unsupported** (do not claim; reevaluate after oracle sound) |

## Counterexample (P0A) — reproduced

Instance: `make_tiny_generic_instance(n_customers=3, n_vehicles=1)`, first action `D_N0_exploit`.

Feasible continuation: serve C0 → travel N0→N1 → accept C1 (announced at t=2) → serve C1 → return N1→D.

| Quantity | Value |
|----------|-------|
| Expected operational reward (θ∈{0,1}) | **14.625** (14.65 / 14.60) |
| Legacy TEI bound (post-travel announced only) | **9.85** |
| Trivial safe reward UB | **20.85** (≥ continuation) |

Sources:

- `src/safe_time_evrp/dr_dual/generic/counterexamples.py`
- `evaluate_generic_resource_bound_legacy_unsafe` / `evaluate_trivial_safe_reward_bound` in `general_bound.py`
- Regression: `tests/test_dr_dual_urgent_repair.py::test_five_action_continuation_reproduces`

**Mathematical defect:** the old TEI envelope formed the pending-customer set from the *post-first-travel* announced/accepted sets only, without advancing announcement events inside the horizon. Positive future service rewards were omitted → bound can lie **below** a feasible nonanticipative value → **not** a valid upper bound, and must not certify `PROVEN_INFEASIBLE`.

Additional hazards retained only in the legacy helper (not used for pruning): one-charge / state-cutoff / single-vehicle reachability. Cutoffs must return `unknown`, never proof of infeasibility (`_optimistic_reach`).

## What was changed

### 0A — Quarantine

- `evaluate_generic_resource_bound` → always `UNSUPPORTED_BOUND` with note `QUARANTINED_...`
- Solver `bound_mode=generic` and `combined` use `evaluate_trivial_safe_reward_bound` instead of the unsafe TEI for certified pruning paths
- Trivial UB: all customers eligible by horizon release time; ignore nonnegative future costs; same first-travel objective term as the oracle

### 0B — Honest oracle statuses (`exact_dp.py`)

- `EXACT_OPTIMUM_RESTRICTED` | `EXACT_OPTIMUM_FULL_FINITE` | `FEASIBLE_INCUMBENT` | `UNKNOWN` | `TIME_LIMIT`
- Truncated plan generation **never** maps empty search → `PROVEN_INFEASIBLE`
- Legacy `OracleStatus.EXACT_OPTIMUM` mapping retained only as “restricted class” for older callers

### 0C — Admission & episode lifecycle (`actions.py`, `closed_loop.py`)

- `fleet_accept_actions`: ACCEPT/REJECT after announcement, independent of vehicle location
- `SERVE` still requires physical presence + acceptance
- `episode_complete`: false while `pending_future_releases`; requires depot return when contracted
- Closed-loop continues until episode complete (not merely empty accepted set)

### 0D — Event / belief reference (`event_oracle.py`)

- Belief-state DP over `legal_fleet_actions` with global announcement clock
- `EXACT_OPTIMUM_FULL_FINITE` only inside declared depth/node limits on that finite action class
- Incomplete search → `TIME_LIMIT` / `FEASIBLE_INCUMBENT` / `UNKNOWN`

### P1 — Discriminating suite (`discriminating_suite.py`)

| ID | Intent |
|----|--------|
| D1_multi_accept | Later announcement + accept away from node + two services |
| D2_two_ev | Two start depots / both vehicles |
| D3_charge | Tight battery → charge before optional customer |
| D4_info | Observation-sensitive energy corridor |

`compute_scaling` now runs this suite (not the degenerate 8×9.75 frozen seeds as the behavioral study).

## Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py tests/test_dr_dual_validation.py tests/test_dr_dual_advance.py tests/test_dr_dual_generic.py tests/test_dr_dual_urgent_repair.py
python -c "from safe_time_evrp.dr_dual.generic.counterexamples import *; print(five_action_multi_customer_continuation()); print(old_bound_undercounts_future_announcement())"
python -m safe_time_evrp.dr_dual.generic.compute_scaling
```

## Scientific answers (audit §Final)

1. **Old bound wrong:** omitted future-announcement rewards (and unsafe charge/cutoff/fleet reachability) → can undercount feasible \(Q\).
2. **Five-action counterexample:** **yes**, expected reward 14.625; legacy bound 9.85.
3. **Oracle exhaustive?** Restricted continuation solver = exhaustive **only** inside declared caps (`EXACT_OPTIMUM_RESTRICTED`). Event belief DP = exhaustive on `legal_fleet_actions` within depth/node limits (`EXACT_OPTIMUM_FULL_FINITE` when completed).
4. **Admission / releases / chronology:** fleet ACCEPT + `global_clock` releases + `episode_complete` await future releases — implemented and tested.
5. **Causal fleet information:** belief updates only via `apply_action` after completed travel; history keys exclude hidden θ. Full multi-vehicle busy-interval event queue is still simplified (idle WAIT sync).
6. **Distinct decisions on varied instances:** **yes on exact values/actions** — D1=14.625, D2=17.45, D3=9.65, D4=12.525 with D4 selecting `D_N0_inform`; info-gain differs from exact on D1. Solver+trivial-bound path still incomplete (2/4 agree; D2 first=`None` under generic mode).
7. **New TEI sound?** **No** — quarantined. Trivial safe UB is sound but loose.
8. **Saves compute?** **Not claimed.** Prior generic TEI screen failed; trivial UB is for safety, not acceleration evidence.
9. **Unsupported:** repaired tight TEI; fully general continuous EVRP; Schneider/Amazon; anytime deadline-sensitive policy-tree contribution.
10. **Possible paper contribution (future):** sound deadline-sensitive / information-aware MPC search on a *correct* finite-state dynamic EVRP with verified nontrivial instances — only after oracle + bound + compute frontier are jointly established.

## Non-negotiable

Do not rewrite earlier negative pruning results. Do not start Schneider / EVRP-TW-D / Amazon until soundness **and** usefulness clear the bar again.
