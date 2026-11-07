# Gate 3F — Matched diagnostic

Script: `scripts/run_gate3f_diagnostic.py`  
Artifacts: [`matched_diagnostic.json`](matched_diagnostic.json), [`matched_summary.json`](matched_summary.json)

## Controllers (honest labels)

| Key | Label |
| --- | --- |
| myopic | myopic_feasible_routing |
| rh_open_loop | deterministic_receding_horizon_mpc |
| rollout | deterministic_prefix_rollout |
| flexibility_mpc | flexibility_terminal_ablation (negative control) |

## EVRP-TW-D middle regime (n=4)

| Metric | myopic | RH | rollout | flexibility |
| --- | ---: | ---: | ---: | ---: |
| mean service rate | 0.05 | 0.70 | 0.70 | 0.70 |
| mean commitment violations | 0 | 0 | 0 | 0 |
| flex≡rollout sequences | — | — | — | 100% |

Mean offline upper-bound rate: **0.70** (controllers meet the constructive UB on average for RH/rollout/flex).

## Amazon

Light and energy-active configs remain fully served (UB=1.0) on the 3×10-stop subset. Charging appears under energy-active; payload unlimited and depot charger remain modeled limitations. Conflicting package-window intersections are **excluded**, not silently widened.
