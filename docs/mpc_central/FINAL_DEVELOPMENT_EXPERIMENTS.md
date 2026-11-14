# Final development experiments

Artifact: [`final_development_results.json`](final_development_results.json)

Holdout: **frozen / unevaluated**.

## Protocol

Controllers (matched seeds, forecasts, releases):

1. B1 reactive ALNS  
2. M1 certificate-carrying ALNS  
3. Ordinary stochastic MPC (same candidates/forecasts)  
4. CC-E-MPC  
5. CC-E-MPC without forecasting  
6. CC-E-MPC without persistent certificate (diagnostic ablation)

Core grid: Phase 3E cases × seeds `{3,7,11}`  
Expansion: same cases × a priori seeds `{13,17,19}` (not chosen by wins)

## Core results (9/9 replay-valid)

| Metric | Value |
|--------|------:|
| Wins vs B1 | 2 |
| Losses vs B1 | 1 |
| Mean Δ completed vs B1 | +0.33 |
| CC-E equals stochastic MPC | 6 / 9 |

Dense seed 7/11: CC-E reaches 8 completions (B1 6). Dense seed 3: CC-E 7 vs B1 8 (loss retained).

## Expansion (`{13,17,19}`)

| Metric | Value |
|--------|------:|
| Wins vs B1 | 2 |
| Losses vs B1 | 1 |
| Mean Δ completed vs B1 | **−0.22** |
| Equals stochastic | 4 / 9 |

Gains do **not** robustly persist under seed expansion (mean completed delta negative).

## Novelty / identity

EV selection among certificate-feasible actions largely overlaps ordinary stochastic MPC (6/9 identical core outcomes). Distinguishing closed-loop cells are real but not a broad superiority claim.

**Paper-facing contribution under `CERTIFICATE_ONLY`:** persistent executable certificates, event-driven advancement under noninterruptible EV actions, hard admission gating, and the nominal feasibility theorem — with economic MPC as the surrounding control law, not as a proven new dominance result over stochastic rollout.

## Final label

**`CERTIFICATE_ONLY`** — do not launch another stochastic-policy redesign; finish the certificate-centered technical draft.
