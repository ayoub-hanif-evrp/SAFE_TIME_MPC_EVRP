# Gate 3F — Forecast noninterference

## Quarantine

`build_scenarios_for(instance=...)` raises if passed a live evaluation instance (eval dues previously leaked day horizon). Online code must call `build_anonymous_scenarios(model, day_horizon=...)` with a horizon from train stats or a fixed policy constant.

## Claim scope

Gate 3F remains **single-scenario anticipatory** planning (`scenario_index=0` by default). It is **not** stochastic multistage / scenario-tree MPC.

## Tests

`tests/test_gate3f_validity.py` mutates hidden customer identities, locations, dues, and counts; controller first actions / plant-relevant route prefixes match under a fixed forecast seed.
