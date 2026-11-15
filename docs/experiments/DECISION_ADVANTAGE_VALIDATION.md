# Decision-advantage validation (Stage 3 — in progress)

**Module:** `src/safe_time_evrp/mpc_central/decision_advantage.py`

## Implemented

- Paired causal advantage \(\widehat{A}(o,a)\) under shared scenarios.
- Interpretable feature score for cheap screening (SoC slack, idle capacity, charge legs, accepts).

## Not yet demonstrated (gate)

- Offline training corpus of (state, incumbent, alternative, paired Δ) on train/dev only.
- Better ranking than hand features on **untouched development** states.
- Confidence / confirmation-scenario override rule replacing the fixed margin.
- Integration into a new selectable controller that beats greedy-nominal on development.

**Stage 6 remains blocked** until this gate passes.
