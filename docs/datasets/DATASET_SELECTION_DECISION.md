# Dataset selection decision (locked after validity repair)

**Git context:** repair work after Schneider v1 study on `main` @ `3a57970`.  
**Decision date:** 2026-11-14.

## Factual recommendation

| Role | Dataset | Rationale |
|------|---------|-----------|
| **Primary EVRP benchmark** | **Schneider-derived dynamic EVRPTW protocol v2** | Established EV windows/battery/chargers; v2 fixes announcement clamping, fleet-cap honesty, and forecast calibration hooks |
| **Secondary temporal realism** | **LaDe** (local `delivery_jl.csv`; LaDe-P conceptually) | Real courier event intensity / geography; **must not** treat `accept_time` as exogenous request creation without evidence |
| **External operational check** | **Amazon Last Mile** (subset) | Real travel-time matrices; EV fields are **modeled electrification**, not measured batteries |
| **Energy plausibility only** | KU Leuven BEV / ESOGU-ML5EV | Not routing/admission benchmarks |
| **Not primary** | EVRP-TW-D | Archive is Solomon + **2-norm**, not the advertised road-edge tables |
| **Unavailable** | EVRPTW-ARC | Access-restricted |

## Source-by-source compatibility audit

### Schneider E-VRPTW
- **Local:** verified zip + 92 extracted instances.  
- **Provides:** Euclidean EVRPTW physics.  
- **Does not provide:** online request arrivals (must be generated and labeled *derived*).  
- **v1 issue:** clamped announcements + fleet cap 6 + forecast μ=12 mismatch + simulator stall on zero-duration arcs.  
- **v2:** no clamp; classify late; fleet cap 20 with flag; calibrated μ; stall repair in `FleetSimulator._start_travel`.

### EVRP-TW-D (Zenodo / local `EVRP-TW-D-B-v1.0.tar.gz`)
- Metadata advertises road networks / territories.  
- **Observed archive:** `dataset/{anchored,unanchored}/Cus_*/solomon` text + pickles with `dist_fun=2-norm`; **no road-edge tables**.  
- Parser already labels `evrp_tw_d_2norm_source`.  
- **Decision:** secondary geometry source at most; not a clean road-network MPC upgrade.

### LaDe (local `data/raw/lade/delivery_jl.csv`)
- Columns include `accept_time`, `accept_gps_*`, `delivery_time`, coordinates, `aoi_*`.  
- **No** dedicated customer-request-creation / release timestamp field in this file.  
- `accept_time` is a courier/task acceptance event — **not** proven exogenous request availability.  
- **Decision:** use for temporal intensity / spatial pattern studies with explicit assumption statements; do not silently equate accept→release.

### Amazon Last Mile (local subset)
- Real `stops` and travel-time matrices; departure timestamps.  
- Electrification via `ElectrificationConfig` (modeled kWh), not observed EV SoC/charging.  
- **Decision:** external sensitivity / travel-time realism; label modeled EV clearly.

### ESOGU-ML5EV / KU Leuven BEV
- Measured energy dynamics archives present locally.  
- **Decision:** calibrate/validate energy assumptions only.

### EVRPTW-ARC
- Empty local dir; manifest `access_restricted`.  
- **Decision:** cannot use until files are obtainable.

## What was confounding v1 conclusions

1. **Simulator stall** on instantaneous depot↔charger arcs → many false failures.  
2. **Forecast misspecification** (fixed μ=12 vs horizon/n-dependent plant μ).  
3. **Benchmark design** (announcement clamp; fleet cap 6 on 100-customer targets).

After repair, remaining gaps (if any) can be attributed more honestly to **control/forecast value** versus software or protocol artifacts.

## Locked design (no large campaign in this repair)

- Keep v1 results immutable for history.  
- Develop on **protocol v2** + stall-fixed simulator.  
- Run only the **fixed diagnostic sample** in `forecast_stall_diagnostic` before any future full evaluation.  
- Do not retune CC-E-MPC / B1 / M1 objectives to chase scores.
