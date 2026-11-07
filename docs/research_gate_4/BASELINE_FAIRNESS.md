# Gate 4 — Baseline Fairness

## Problem with Gate 3F comparison

The ~5% myopic vs ~70% RH gap mixed two effects:

1. Planning **already announced** customers before their service windows open.
2. Using **anonymous forecasts** of unreleased demand.

A competent nonclairvoyant router does (1) without (2).

## Controllers (honest labels)

| Kind | Label | Forecasts | Announced-not-ready |
|------|-------|-----------|---------------------|
| `myopic` | `weak_ready_only_myopic` | ignored | **excluded** |
| `reactive` | `reactive_announced_commitment_preserving` | ignored | **included** |
| `rh_open_loop` | `deterministic_receding_horizon_mpc` | anonymous | included |
| `rollout` | `deterministic_prefix_rollout` | anonymous | included |
| `flexibility_mpc` | `flexibility_terminal_ablation` | anonymous | included |

## Fair predictive-value test

Compare **reactive** vs **RH / stochastic lookahead** under identical physics, acceptance gate, horizon, and compute budget. Attribute improvement to forecasts only when RH beats reactive.

Do not cite weak myopic as a state-of-the-art baseline.

## Exploratory Gate 4 diagnostic

`scripts/run_gate4_diagnostic.py` reports `rh_minus_reactive` under preregistered \(\mu\). Results are exploratory, not holdout evaluation.

On the generating revision recorded in `matched_summary.json`, **mean `rh_minus_reactive` was 0.0** across 24 EVRP-TW-D development rows. Under these preregistered announcement specs, anonymous-forecast RH did not improve completed service over the strong reactive baseline. This supports treating Gate 3F’s myopic gap as largely baseline artifact.
