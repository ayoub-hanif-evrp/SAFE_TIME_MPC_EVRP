# Scientific status (corrected)

**Historical note:** Commit `e1f9f0a` reported PROMISING METHOD. An independent audit found an invalid incumbent lower bound, nonanticipativity bugs, and an unsound zero-VoI test. Those are repaired in this tip; see `CORRECTION_AUDIT.md`. Prior docs remain as artifacts.

## Current verdict: **CORRECTED PROTOTYPE — CONDITIONAL PROMISE**

Not a top-tier claim. Not a topic switch.

### What now holds

1. Nonanticipative common continuation policy selection (same plan for identical observation histories).
2. Incumbent L = executable Bayes value only (P1/P2 regression documents why `min max` is illegal).
3. Zero-VoI certificate withdrawn from certified pruning.
4. Clairvoyant DRUB retained as a **reference** upper bound; pruning uses it only with verified L.
5. Resource envelope bound implemented and instrumented; certified prune only if it dominates clairvoyant on the instance (often does not).
6. Full compute counters (known-θ calls, common-policy evals, bound evals), not only first-action expansions.
7. Commitment completion, busy_until, payload checks.

### What does not hold yet

- Demonstrated cross-vehicle information value under a shared global clock.
- A cheap resource bound that is both sound and routinely tighter/cheaper than clairvoyant DRUB.
- Multi-instance computational advantage beyond the hand-built corridor toy.
- Dynamic request release in the primary exact table.

### Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; print(write_artifacts(Path('docs/decision_relevant_dual_mpc'))['pruning_ablation'])"
```
