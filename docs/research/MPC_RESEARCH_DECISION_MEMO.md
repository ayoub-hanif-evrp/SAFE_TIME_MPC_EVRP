# Research decision memo — Schneider + Hanif (EVRP-TW-D retired)

**Date:** 2026-11-19  
**Active datasets:** Schneider EVRPTW (primary economics) + Hanif/Homberger charging (latency / large-scale)  
**Retired:** `evrp_tw_d` — all EVRP-TW-D result artifacts removed from `docs/experiments/`

## Identity (frozen)

One controller: commitment-safe RH MPC + SPI + M1–M4 + Schneider family-fit forecasts (+ MSA/adaptive packaging in `mpc_top_tier_msa_v1`).

## Headline results (kept)

| Role | Outcome |
|---|---|
| Schneider recovery-dev / holdout_v2 (`mpc_multi_dataset_recovery_v2_forecast`) | **PASS** NI (holdout CI low ≈ +79) |
| Schneider under MSA defaults (recovery-dev / holdout_v3) | **FAIL** — sensitivity; do not claim |
| Homberger/Hanif latency @ budget 2.0s | **PASS** (p50 ≈ 1.71; 0 fails) |
| EVRP-TW-D | **Retired — results deleted** |

## Publishable stance

1. **Schneider** = economic core.  
2. **Hanif/Homberger** = large-scale charging companion (latency appendix unless/until ops KPI freeze is run).  
3. **No EVRP-TW-D claims.**

## Artifacts

- `docs/experiments/MPC_MULTI_DATASET_RECOVERY_RESULTS.*` (Schneider)
- `docs/experiments/MPC_TOP_TIER_MSA_RESULTS.*` (scrubbed)
- `docs/experiments/MPC_HOMBERGER_LATENCY.*`
