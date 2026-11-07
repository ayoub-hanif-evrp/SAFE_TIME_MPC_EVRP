# Scientific status

## Verdict: **PROMISING METHOD** (narrow, provisional)

A sound DRUB-style upper bound, tied to the same continuation family as the exact oracle, **prunes a decision-irrelevant informative corridor** while **retaining the exact safe-dual first action** on the single-EV network (3→2 expansions in the matched ablation). Charging is an explicit `CHARGE_FULL` action; corridors are distinct physical segments; passive baseline is optimized under forced-prior continuations.

## What is still weak for a top-tier paper

1. DRUB is close to a clairvoyant-after-\(\theta\) open-loop relaxation — the generic pruning inequality is not new; the EVRP-specific content is the zero-VoI / TW–SOC certificate and the commitment-safe action set.
2. Cross-vehicle information value is **not** cleanly demonstrated on the current 2-EV calibration.
3. No Schneider/EVRP-TW-D/Amazon development campaign yet (by scope limit).
4. Partial charging and nonzero-noise Bayes optimality not fully certified.

## Preserved negatives

Gate 4 commitment-cost NO-GO and safe-dual STOP/human-decision reports remain unchanged in their directories.

## Next human-led steps (same algorithm — no topic switch)

- Tighten DRUB with cheaper resource envelopes that avoid enumerating \(V_{\mathrm{OL}}\).
- Retune 2-EV instance until shared-θ inform changes EV2’s charge decision under exact search.
- Only then expand development instances.

## Commands / commit

```bash
python -m pytest -q tests/test_dr_dual.py
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; print(write_artifacts(Path('docs/decision_relevant_dual_mpc'))['pruning_ablation'])"
```
