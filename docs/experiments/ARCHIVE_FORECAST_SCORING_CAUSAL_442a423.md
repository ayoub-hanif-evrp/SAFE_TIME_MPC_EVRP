# Archive — forecast scoring causal results (SHA `442a423`)

**Source commit:** `442a42329d283bad14f1900eac6a37ab33b6e0cb`  
**Artifacts (frozen at that SHA):**

- `docs/experiments/forecast_scoring_causal_results.json`
- `docs/experiments/FORECAST_SCORING_CAUSAL_AUDIT.md`

**Headline (exploratory, not confirmatory):**

| Controller | Mean completed (n=18) |
| --- | ---: |
| `cce_greedy_nominal` | 6.67 |
| `m1` | 4.89 |
| `b1` | 3.94 |
| `cce_causal_empty_future` | 4.44 |
| `cce_conditional_calibrated` | 3.89 |

**Supported conclusion at archive time:** `negligible_decision_value` for conditional forecast vs causal empty-future under identical causal scoring. Greedy-nominal remains a strong exploratory reference (unequal objective vs causal modes).

Do not overwrite these files as “fresh” validation after methodology changes; new comparisons live under `FINAL_COMPETITIVE_COMPARISON.*`.
