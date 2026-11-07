# Gate 3E — Matched development results

Script: `scripts/run_gate3e_matched_retest.py`  
Artifacts: [`matched_results.json`](matched_results.json), [`matched_summary.json`](matched_summary.json)

## Controller labels

| Code key | Honest label |
| --- | --- |
| myopic | myopic_feasible_routing |
| rh_open_loop | deterministic_receding_horizon_mpc |
| rollout | deterministic_prefix_rollout |
| flexibility_mpc | flexibility_terminal_ablation |

## EVRP-TW-D Cus_5 dev (n=4, seed fleets, anonymous forecasts)

Mean served ≈ 0.75 for all four controllers; commitment violations 0; replay 100%; flex≡rollout 100%.

Service rates are low under tight native windows + information-safe synthetic releases. This is an honest difficulty signal, not a myopic-vs-RH win under privileged forecasts.

## Amazon

| Config | n | mean served | mean charges | flex≡rollout |
| --- | ---: | ---: | ---: | ---: |
| esogu_light_cargo_v1 (0.15 kWh/km) | 3 | 10 | 0 | 100% |
| esogu_energy_active_v1 (0.50 kWh/km, modeled) | 3 | 10 | 1.0 | 100% |

0.50 kWh/km is a **modeled uplift** to activate charging, not measured ESOGU consumption. Charger is synthetic and depot-colocated.

## Executable horizon microscope

Short H executed first action: **A service**. Long H: **S charge**. Planned long-H first stop may be `syn_*` but is stripped before dispatch; claim uses executed action only.
