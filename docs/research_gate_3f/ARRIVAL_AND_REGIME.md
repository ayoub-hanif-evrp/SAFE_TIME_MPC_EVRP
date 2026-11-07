# Gate 3F — Arrival semantics and operating regime

## Poisson announcements

`synthetic_poisson_releases` now uses exponential interarrivals

`Δt = −μ log(1−U)`,

not the Gate 3E affine-uniform map. Announcement time is **not** clamped to `window.ready` or `window.due`.

Service windows remain plant constraints. Late announcements may be a-priori unserviceable and are counted in the denominator via `offline_service_upper_bound`.

## Offline upper bound

Announcement-aware constructive bound: clone ready ← max(window.ready, announcement), then static insertion under nominal energy. This avoids vacuous 100% bounds that ignore late announcements.

## Middle regime

Diagnostic searches train-μ scales where upper-bound service rate ∈ [0.40, 0.80] and a-priori impossible fraction ≤ 50%.

Matched diagnostic (see `matched_summary.json`): **4** EVRP-TW-D middle-regime cases with mean upper-bound rate **0.70**. RH/rollout/flexibility achieve ~0.70 service rate; myopic ~0.05. Amazon remains saturated (UB=1.0) under current subset/electrification.
