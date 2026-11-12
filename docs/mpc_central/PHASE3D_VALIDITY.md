# Phase 3D — Validity repairs

**Date:** 12 November 2026  
**Prior tip reviewed:** `bf8838d` (Phase 3C REVISE)

## Priority 1 — Plant evaluation contract

| Issue | Repair |
|-------|--------|
| `depart` records lack `distance`; plant used `data.get("distance")` → zero penalty | Score via `executed_distance_from_log` (authoritative arc table) |
| Scenario recourse used forecast-blind `EventTriggeredMPC` after first action | Default `recourse='b1_validated'` (`B1ValidatedRecourse`); `insertion` kept as labeled baseline |
| `max_replan_interval` unused in causal plant | Periodic `schedule_replan` / cancel matching `run_episode` |
| Phase 3B/3C values under zero distance | Regenerated in `phase3d_results.json` → `repaired_fork_values` and fairness suite |

### Effect on earlier results

Absolute action values change (distance penalty now nonzero). On the three microscopic forks, **action rankings are preserved** in the repaired plant (charge ≻ serve; reject ≻ accept). Decision-regret *winner labels* for adaptive vs uniform remain order-fragile at budget 3 (negative evidence retained).

Regression: `tests/test_mpc_central_phase3d.py` asserts nonzero executed distance and ranking preservation.

## Priority 2 — Scenario-value estimation

| Issue | Repair |
|-------|--------|
| `sampled_expectation` renormalized over sampled scenarios only | Prior-weighted fill with `missing_fill=0` (no renormalization) |
| Adaptive compared only to hand-made uniform | Added `equal_allocation` (classical R&S) and `paired_common_random` (CRN pairing) |
| Classic OCBA | **Not** applied: plant values are deterministic given scenario index (zero within-design variance) |

Offline oracle remains offline-only. Reference label:
`exhaustive_first_action_ranking_under_causal_b1_validated_recourse`
(not a global multistage MPC oracle).

## Priority 3 — Controller

`CommitmentSafePredictiveMpc` (`commitment_safe_mpc/predictive_mpc.py`):

1. Public snapshot observation  
2. Revalidate / retain continuation witness  
3. ALNS + insertion candidate proposals  
4. Independent nominal validation; strip unvalidated new accepts  
5. Train/development anonymous forecast scenarios (information-safe)  
6. Forecast lookahead scoring under cooperative wall-clock budget  
7. Select best validated candidate; verified fallback if optimization stops early  
8. Execute via `run_episode` (same plant)

ALNS is a candidate generator. MPC selects on predicted closed-loop consequences.

## Priority 5 — Documentation / AU residual

- `PHASE3C_FAIRNESS_AUDIT.md` reconciled to JSON: **18** comparisons, **15** ties.  
- Fulfillment audit can distinguish cutoff from residual infeasibility via
  `residual_continuation_feasible` / `cutoff_vs_infeasibility` flags.

## What is supported vs unproved

See `PHASE3D_CLOSED_LOOP_RESULTS.md` and `phase3d_results.json` → `scientific`.
