# Finite-demand forecast calibration

**Protocol:** `2026-11-14.v2`

- Sum realized dynamic arrivals (dev segments): **132.00**
- Sum predicted (finite model): **132.00** (ratio 1.000)
- Sum predicted (old Poisson-over-horizon): **1228.78** (ratio 9.309)

Finite model uses train empirical announce-time fractions * mean dynamic count. Poisson uses homogeneous rate over the full horizon (old misspecification).

A successful correction requires the finite ratio near 1 and far below the Poisson over-prediction ratio — not merely a re-fit of μ.

## Honesty (Stage 1D)

Pooled predicted==realized totals can be partly mechanical when \(N\) and dynamicity
fractions are known. Prefer:

- segment mean absolute error (`mean_abs_segment_error_finite` / `_poisson`);
- size-stratified totals (`totals_by_customer_count`);
- temporal survival / active-end behavior;

over the pooled ratio alone. See `calibration_report_finite_vs_poisson` → `honesty_note`.
