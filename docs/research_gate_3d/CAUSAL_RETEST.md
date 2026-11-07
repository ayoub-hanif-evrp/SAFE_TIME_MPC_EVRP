# Gate 3D — Matched causal re-test

Harness: `FleetSimulator` + `mpc3c/sim_experiment.compare_controllers`.  
Script: `scripts/run_gate3d_causal_retest.py`.  
Artifacts: [`causal_results.json`](causal_results.json), [`causal_summary.json`](causal_summary.json).

## Setup

- **EVRP-TW-D Cus_5:** fleet size = seed-required fleet from Gate 3C `evrptwd_seeds.json` (not fixed 2). Native Q. Synthetic Poisson-like releases; forecasts fitted on train-split ready gaps only.
- **Amazon:** real UTC windows when parseable; `esogu_energy_active_v1` (0.50 kWh/km, 40 kWh, 12 stops).
- Controllers: myopic, RH open-loop, rollout, flexibility (repaired info). Identical streams and compute budgets per case.
- Metrics: full-episode action Hamming / decision-event diffs, customers served, commitment violations, charge events, distance, runtime, replay_ok.

## Aggregate (mean customers served)

| Pool | n | myopic | RH | rollout | flexibility | flex≡rollout seq |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EVRP-TW-D Cus_5 dev | 4 | 0.50 | 4.50 | 4.25 | 4.25 | 100% |
| EVRP-TW-D Cus_5 held-out | 4 | 0.75 | 3.25 | 4.00 | 4.00 | 100% |
| Amazon energy-active | 4 | 12.0 | 12.0 | 12.0 | 12.0 | 100% |

- Flexibility vs RH first-action divergence: **0%** on all pools.
- Flexibility vs rollout sequence: **identical** on all cases.
- Replay OK: **100%**.
- Amazon charge-event probe: **4/4** routes record ≥1 charge under energy-active config (fraction 1.0).
- EVRP-TW-D charge events appear under RH/rollout/flexibility on some seed fleets (mean ~0.25).

## Horizon microscope

See [`HORIZON_CAUSALITY.md`](HORIZON_CAUSALITY.md): increasing \(H\) changes the present action (A→B) under forecasts.

## Notes

- Myopic underperforms on tight EVRP-TW-D windows with synthetic early releases (horizon/forecast value is real here).
- No new MPC mechanism was introduced; flexibility remains the Gate 3C terminal with an information-correct remaining set.
