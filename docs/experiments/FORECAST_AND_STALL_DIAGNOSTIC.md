# Forecast and stall diagnostic

**Protocol:** `2026-11-14.v2`  
**Stems:** c101C5, c104C10, c106C15, r104C5, r103C10, r105C15, rc105C5, rc108C10, rc108C15  
**Environment realizations per stem:** 2  
**Stall count:** 0  

## Calibration (train-only)

```json
{
  "protocol_version": "2026-11-14.v2",
  "dynamicity": "medium",
  "n_train_stems": 9,
  "n_realizations_per_stem": 3,
  "n_gap_samples": 27,
  "calibrated_announcement_mean": 7.235932687000066,
  "late_for_depot_admit_rate": 0.014814814814814815,
  "policy_seed_helper": "policy_seed_for",
  "environment_seed_note": "v2 diagnostic XORs frozen v1 env seeds to avoid accidental reuse"
}
```

## Mean completed services

```json
{
  "misspecified_cce": {
    "n": 18,
    "mean": 3.888888888888889
  },
  "calibrated_cce": {
    "n": 18,
    "mean": 4.222222222222222
  },
  "cce_no_forecast": {
    "n": 18,
    "mean": 6.666666666666667
  },
  "b1": {
    "n": 18,
    "mean": 4.388888888888889
  },
  "m1": {
    "n": 18,
    "mean": 4.888888888888889
  },
  "stochastic_misspecified": {
    "n": 18,
    "mean": 3.2222222222222223
  },
  "stochastic_calibrated": {
    "n": 18,
    "mean": 4.0
  }
}
```

## Failures

```json
{}
```

## Reading

- Stall target met: **0** `decision loop did not advance time` failures on this sample after
  repairing zero-duration arc handling in `FleetSimulator._start_travel`.
- Train-calibrated announcement μ ≈ **7.24** (vs misspecified 12). Late-for-depot-admit rate on
  calibration draws ≈ **1.5%** (classified, not clamped).
- On this fixed 9×2 sample, mean completed services:
  - CC-E misspecified 3.89 → calibrated **4.22** (small uplift)
  - stochastic misspecified 3.22 → calibrated **4.00**
  - **CC-E no-forecast 6.67** still highest among CC-E variants; M1 4.89; B1 4.39
- **Attribution (this diagnostic only):** after removing simulator stalls and aligning μ,
  forecast-using CC-E-MPC still does **not** beat its no-forecast ablation. Remaining gap looks
  primarily **methodological / decision-relevance of the forecast**, not unexplained simulation
  crashes or announcement clamping.
- Perfect-information block is diagnostic only and non-deployable.
- Prior 36×5 v1 Schneider results remain frozen; this sample is **not** fresh final validation.
