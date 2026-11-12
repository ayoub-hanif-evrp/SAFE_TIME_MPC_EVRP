# Phase 3D — Validity repairs

**Date:** 12 November 2026  
**Commit series:** `94b226e` + follow-up completeness commit  
**Prior tip reviewed:** `bf8838d` (Phase 3C REVISE)

## Priority 1 — Plant evaluation contract

| Issue | Repair |
|-------|--------|
| `depart` records lack `distance`; plant used `data.get("distance")` → zero penalty | Score via `executed_distance_from_log` (authoritative arc table) |
| Scenario recourse used forecast-blind `EventTriggeredMPC` after first action | Default `recourse='b1_validated'` (`B1ValidatedRecourse`); `insertion` kept as labeled baseline |
| `max_replan_interval` unused in causal plant | Periodic `schedule_replan` / cancel matching `run_episode` |
| Phase 3B/3C values under zero distance | Regenerated in `phase3d_results.json` → `repaired_fork_values` and fairness suite |

### Effect on earlier results

Absolute action values change (distance penalty now nonzero). On the three microscopic forks, **action rankings are preserved**. Decision-regret adaptive-vs-uniform wins remain order-fragile at budget 3 (negative evidence retained).

## Priority 2 — Scenario-value estimation

| Issue | Repair |
|-------|--------|
| `sampled_expectation` renormalized over sampled scenarios only | Prior-weighted fill with `missing_fill=0` (no renormalization) |
| Adaptive compared only to hand-made uniform | Added `equal_allocation` and `paired_common_random` |
| Classic OCBA | **Not** applied: plant values are deterministic given scenario index |

## Priority 3 — Controller with causal rollouts

`CommitmentSafePredictiveMpc` + `mpc_central/scenario_rollout.py`:

1. Public snapshot observation  
2. Revalidate / retain continuation witness  
3. ALNS + insertion candidate proposals  
4. Independent nominal validation; strip unvalidated new accepts  
5. Train-only anonymous forecast scenarios (`phase3d_splits.fit_train_forecast`)  
6. **Causal closed-loop scenario rollouts** (seed plant from observation anchors, inject forecast releases, B1-validated recourse, same scoring as `causal_plant`)  
7. Select best validated candidate under cooperative wall-clock budget  
8. Verified fallback if optimization stops early  
9. Execute via `run_episode`

## Priority 4 — Splits

| Split | Cases | Use |
|-------|-------|-----|
| Train | `B_tight_battery`, `B_competing` | Forecast fitting only |
| Development | `B_phase_b`, `B_easy_dynamic` | Closed-loop pilot |
| Holdout | `B_adversarial_overaccept` | **Untouched** |

## Priority 5 — AU residual feasibility

Artifact: [`phase3d_au_residual.json`](phase3d_au_residual.json)

Re-ran all 31 frontier AU source rows. For each episode with accepted-unfulfilled, residual probes try verified witness → last decision routes → insertion residual plan at the final observation.

| Metric | Value |
|--------|------:|
| Audited | 31 |
| Cutoff + AU (reproduced) | 21 |
| No AU on re-run (non-reproduction) | 10 |
| Cutoff with feasible residual continuation | 0 |
| Cutoff with infeasible/unknown residual | 21 |

**Interpretation:** Identifying cutoff is not enough. In this audit, residual nominal probes also failed for every reproduced AU-cutoff episode — evidence of lost feasible continuation (or probe weakness), not mere time censoring alone.

## What is supported vs unproved

See `PHASE3D_CLOSED_LOOP_RESULTS.md` and `phase3d_results.json` → `scientific`.
