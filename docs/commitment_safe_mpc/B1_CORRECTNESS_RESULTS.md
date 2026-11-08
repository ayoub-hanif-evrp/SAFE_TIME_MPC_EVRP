# B1 correctness results

Artifact: `baseline_comparison_b0_b1.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --b1`

## Controllers (matched)

| ID | Implementation |
|----|----------------|
| Insertion | `EventTriggeredMPC` |
| B0 | `ReactiveAlnsMpc` |
| B1 | `FullValidationAlnsMpc` (wraps B0 ALNS + independent validation) |

Same plant, releases, fleet, horizon, replan interval, ALNS budgets (`iterations=30`, cooperative `time_limit_seconds=0.2`), seed 7.

## Summary

| Metric | Value |
|--------|-------|
| Cases | 5 |
| Insertion + B0 replay-ok | **5/5** |
| B1 replay-ok | **5/5** |
| B1 certified-feasible decisions (sum over suite) | Present on every case (see JSON `certified_feasible_decisions`) |
| Executed distance | Insertion = B0 = B1 on this suite |
| Completed sets | Matched across controllers on this suite |

## Adversarial case `B_adversarial_overaccept`

Tight early window on C1 vs far C2. All three controllers complete `{C1, C3}` and reject `C2` (replay-ok). Independent unit test `test_validate_continuation_rejects_commitment_breaking_extra` proves that a C2-first plan breaking C1’s window is **not** certified; B1 therefore cannot accept such a continuation as `CERTIFIED_FEASIBLE`.

## Latency / validation overhead (suite scale)

B1 mean decision times remain on the order of a few milliseconds with tiny validation overhead relative to ALNS search on these toys (see `validation_seconds` and `REVALIDATION_COST_PROFILE.md`). This does **not** claim scalability to Schneider/Amazon sizes.

## Interpretation

B1 is the **full-validation safe baseline** using the same search engine as B0. It is ready as the comparison target for future M1 incremental certificates — M1 is **not** implemented here.
