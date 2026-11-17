# Research decision memo — Commitment-Safe Stochastic MPC

**Date:** 2026-11-17  
**Method freeze:** Commitment-safe stochastic MPC with SPI-over-greedy selection (forecast off), nonlinear piecewise charging plant.  
**Eval protocol:** `mpc_paper_multi_dataset_v1` — **PASS** on Schneider development.

## Controllers (plain paper names)

| Paper name | Role |
|---|---|
| Proposed: commitment-safe stochastic MPC (SPI) | Main method |
| Economic MPC — greedy nominal scoring | Primary economic baseline |
| Full-validation ALNS–MPC | ALNS baseline |
| Certificate-carrying ALNS–MPC | Certificate ALNS baseline |
| Scenario economic MPC (sampled futures) | Predictive baseline |
| Ablation: proposed + demand forecast | Forecast on/off |
| Ablation: proposed without SPI | SPI on/off |

## Dataset roles (same EVRPTW family; not pooled)

| Dataset | Role |
|---|---|
| Schneider E-VRPTW | Primary economic table (development; **test sealed**) |
| EVRP-TW-D | Confirmatory geography (frozen Cus_5 / Cus_15 subset) |
| Homberger + chargers | Latency appendix only |

Loaders map each archive into a common `Instance`; **one method + one plant**.

## Schneider gate (`mpc_paper_multi_dataset_v1`)

| Check | Result |
|---|---|
| Proposed − greedy-nominal \(J\) | mean ≈ **+376**, tally **9 better / 0 worse**, AU mean ≈ **−1.28** → **PASS** (non-inferiority) |
| CI excludes 0? | No → **not** claimed as dominance |
| vs certificate-carrying ALNS | CI low > 0 (significant) |
| SPI vs SPI-off ablation | mean \(\Delta J\) ≈ +215, tally 8/1 (SPI helps) |
| Forecast ablation | Forecast not needed for the proposed claim |
| Compute | p50 ≈ **0.12s** → **PASS** |

Evidence: `docs/experiments/MPC_PAPER_EVAL_RESULTS.md`.

## EVRP-TW-D confirmatory

Frozen 8 cells (4×Cus_5 + 4×Cus_15). Proposed competitive vs greedy-nominal (tally 3/1/4); clearly better than both ALNS baselines on this freeze. **Not averaged with Schneider.**

## Homberger latency

Timed `decide()` on large instances (25 announced customers): proposed p50 ≈ **1.05s**, greedy-nominal p50 ≈ **1.39s**. Appendix only — overruns vs 0.35s cooperative budget are expected at this scale.

## Nonlinear charging

Mechanism demo **holds** (linear planning certifies a near-full top-up that nonlinear rejects). See `docs/experiments/MPC_NONLINEAR_EV_ABLATION.md`.

## Decision

- Claim **non-inferiority** (and strong secondary baselines) on Schneider development; confirmatory geography on EVRP-TW-D; latency on Homberger.
- Do **not** claim CI-excluding dominance, demand-prediction value, recursive feasibility, or Homberger economic ranking.
- Schneider **test split remains sealed** until one final confirmatory run after write-up freeze.
