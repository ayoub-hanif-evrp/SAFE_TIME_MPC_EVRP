# Top-tier readiness — Schneider + Hanif

**Verdict:** `schneider_primary_hanif_latency`  
**Retired dataset:** `evrp_tw_d` (results removed).

| Gate | Status |
|---|---|
| Schneider NI @ recovery compute (`mpc_multi_dataset_recovery_v2_forecast`) | **PASS** (holdout_v2 CI low ≈ +79) |
| Schneider under MSA defaults | **FAIL** (sensitivity; not the claim) |
| Homberger/Hanif latency @ budget 2.0s | **PASS** |
| EVRP-TW-D multi-dataset claim | **RETIRED** |

## Allowed claim

Commitment-safe stochastic MPC with accept discipline and Schneider-fit scenario demand is non-inferior on Schneider under the recovery-validated freeze. Homberger/Hanif supports online decide latency under announced-cap at budget 2.0s.

## Forbidden

EVRP-TW-D claims; pooling; Homberger economic ranking; Schneider NI under MSA/adaptive defaults without new evidence.
