# Top-tier readiness — Commitment-Safe Stochastic MPC (SPI)

**Verdict:** `ready_for_mechanism_noninferiority_paper` (TS/TRC/TRE-style). **Not** ready for Automatica recursive-feasibility / CI-excluding \(J\)-dominance claims.

**Method:** Commitment-safe stochastic MPC with SPI-over-greedy selection; forecast off; nonlinear piecewise charging; certified emission.  
**Evidence:** `docs/experiments/MPC_PAPER_EVAL_RESULTS.md` (`mpc_paper_multi_dataset_v1`), `MPC_NONLINEAR_EV_ABLATION.md`, `MPC_HOMBERGER_LATENCY.md`.

| Gate | Status |
|---|---|
| A Validity | **PASS** (emission soundness; scenario-terminal honesty — not RF) |
| B Mechanism | **PASS** (SPI law; nonlinear vs linear Validate mismatch) |
| C Schneider vs greedy-nominal | **PASS non-inferiority** (mean \(\Delta J\approx+376\), tally 9/0; CI does not exclude 0) |
| C′ vs certificate-carrying ALNS | **PASS** (clustered CI excludes 0) |
| D Computation (Schneider 5–15) | **PASS** (p50≈0.12s) |
| E EVRP-TW-D confirmatory | **PASS transfer** (frozen subset; role-separated) |
| F Homberger latency | **PASS appendix** (decide p50 reported; not economic ranking) |
| G Automatica RF / blanket \(J\) win | **FAIL / deferred** |

## Paper story (frozen)

*Commitment-safe stochastic MPC for dynamic EVRPTW with irreversible accepts: SPI-over-greedy selection, nonlinear charging, certified emission — non-inferior to strong economic MPC on Schneider, confirmed on EVRP-TW-D geography, with Homberger latency appendix; superior where linear charging understates near-full charge time.*

## Do not claim

- Demand-prediction value (forecast ablation does not reclaim it).
- Recursive feasibility.
- Stem-clustered CI-excluding dominance over greedy-nominal.
- Pooled average \(J\) across the three datasets.
- Homberger economic superiority.
