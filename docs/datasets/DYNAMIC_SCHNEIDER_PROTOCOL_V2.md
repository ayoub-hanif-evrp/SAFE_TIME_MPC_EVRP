# Schneider-derived dynamic EVRPTW — protocol v2

**Protocol version:** `2026-11-14.v2`  
**Supersedes for new work:** v1 (`2026-11-14.v1`)  
**Frozen v1 evidence:** `docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json` (do not rewrite)

## Changes versus v1

| Topic | v1 | v2 |
|-------|----|----|
| Announcement times | Clamped to `min(poisson_t, latest_depot_admit)` | **No clamp** — natural Poisson times |
| Late requests | Hidden by clamping | Classified as `late_for_depot_admit` |
| Fleet hard cap | `min(6, …)` | `min(20, …)` with `hit_hard_cap` metadata |
| Forecast μ | Fixed `12.0` (misspecified vs size/horizon μ) | Train-calibrated from training release realizations |

Geometry, windows, chargers, \(Q,C,r,g,v\) remain the Schneider deposit. Controllers/objective weights are unchanged.

## Release generation

1. Shuffle customers with `environment_seed`.  
2. Mark known-at-start fraction by dynamicity table (same fractions as v1).  
3. Draw exponential interarrivals for the rest with  
   \(\mu = \texttt{mean\_interarrival\_scale}\cdot H/n\).  
4. **Do not** modify times for feasibility.  
5. Record `latest_depot_admit = due - service - travel(depot, customer)` and flag lateness.

## Fleet rule

\[
\texttt{fleet}=\min\bigl(20,\ \max(\lceil D/C\rceil,\ \lceil n/5\rceil)\bigr)
\]

If the uncapped target exceeds 20, set `hit_hard_cap=true` and treat the run as computationally constrained — do not swap instances.

## Seed semantics

Unchanged: `environment_seed` → releases only; `policy_seed` → controller RNG; paired controllers share both for a realization.

## Forecast calibration

`calibrated_announcement_mean_from_train` estimates μ from **training stems only** and multiple environment realizations. Predictive controllers may be compared under:

- misspecified μ=12 (v1 behavior)  
- calibrated μ  
- no forecast  
- perfect-information **diagnostic** (non-deployable; no hidden IDs in `decide`)

## Runner

```bash
python -m safe_time_evrp.mpc_central.forecast_stall_diagnostic
```
