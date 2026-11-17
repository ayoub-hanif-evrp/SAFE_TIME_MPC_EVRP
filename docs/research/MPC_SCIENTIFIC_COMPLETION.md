# Scientific completion — remaining gaps

Protocol: development-only; failures included; objective unchanged.

## 1. First-divergence reconstruction

| Stem | Δ econ | Div t | CSS action | GN action | Labels |
|---|---:|---:|---|---|---|
| r103C10 | -1669.6 | 3.79 | (('v1', 'C16', 'service'), ('v2', 'C81', 'service'))/[] | (('v1', 'C16', 'service'), ('v2', 'C81', 'service'))/['C53'] | F_feasibility_or_empty_set,accept_set_divergence |
| rc108C10 | -932.8 | 0.00 | (('v1', '', 'idle'), ('v2', '', 'idle'))/[] | (('v1', 'C80', 'service'), ('v2', 'D0', 'return'))/['C80'] | B_ranking_error,GN_matches_hindsight_CSS_does_not,accept_set_divergence,forecast_empty_disagree_at_divergence |
| rc108C15 | -345.8 | 0.00 | (('v1', '', 'idle'), ('v2', 'S0', 'charge'), ('v3', '', 'idle'))/[] | (('v1', 'C19', 'service'), ('v2', 'D0', 'return'), ('v3', 'D0', 'return'))/['C19'] | B_ranking_error,GN_matches_hindsight_CSS_does_not,CSS_charge_vs_GN_service,accept_set_divergence,forecast_empty_disagree_at_divergence |
| c106C15 | 1929.0 | 0.00 | (('v1', 'C1', 'service'), ('v2', '', 'idle'), ('v3', '', 'idle'))/['C1'] | (('v1', 'C1', 'service'), ('v2', 'D0', 'return'), ('v3', 'D0', 'return'))/['C1'] | GN_matches_hindsight_CSS_does_not |

## 2. EV regime factorial (all cells)

| Stem | Dyn | Regime | Δ econ CSS−GN | CSS comp | GN comp | Failure |
|---|---|---|---:|---:|---:|---|
| r103C10 | low | battery_tight_0.6 | 1470.7 | 5 | 2 |  |
| r103C10 | low | battery_nominal_1.0 | 117.8 | 8 | 7 |  |
| r103C10 | low | battery_generous_1.5 | -1806.2 | 1 | 8 |  |
| r103C10 | low | battery_infinite | -1677.5 | 4 | 9 |  |
| r103C10 | low | chargers_sparse_0.5 | 117.8 | 8 | 7 |  |
| r103C10 | low | charge_slow_x2 | 0.0 | 6 | 6 |  |
| r103C10 | medium | battery_tight_0.6 | 1.2 | 8 | 8 |  |
| r103C10 | medium | battery_nominal_1.0 | -1669.6 | 3 | 8 |  |
| r103C10 | medium | battery_generous_1.5 | 17.6 | 8 | 8 |  |
| r103C10 | medium | battery_infinite | -1192.6 | 1 | 9 |  |
| r103C10 | medium | chargers_sparse_0.5 | 0.3 | 8 | 8 |  |
| r103C10 | medium | charge_slow_x2 | -684.7 | 5 | 7 |  |
| r103C10 | high | battery_tight_0.6 | -195.9 | 6 | 8 |  |
| r103C10 | high | battery_nominal_1.0 | -663.8 | 5 | 8 |  |
| r103C10 | high | battery_generous_1.5 | 19.1 | 8 | 8 |  |
| r103C10 | high | battery_infinite | 8.9 | 9 | 9 |  |
| r103C10 | high | chargers_sparse_0.5 | 129.4 | 9 | 8 |  |
| r103C10 | high | charge_slow_x2 | 211.8 | 9 | 7 |  |
| rc108C10 | low | battery_tight_0.6 | -19.2 | 4 | 4 |  |
| rc108C10 | low | battery_nominal_1.0 | 1299.9 | 5 | 2 |  |
| rc108C10 | low | battery_generous_1.5 | -1028.1 | 2 | 6 |  |
| rc108C10 | low | battery_infinite | -1183.1 | 2 | 8 |  |
| rc108C10 | low | chargers_sparse_0.5 | 1782.6 | 5 | 1 |  |
| rc108C10 | low | charge_slow_x2 | 26.8 | 5 | 5 |  |
| rc108C10 | medium | battery_tight_0.6 | -32.4 | 4 | 4 |  |
| rc108C10 | medium | battery_nominal_1.0 | -932.8 | 4 | 7 |  |
| rc108C10 | medium | battery_generous_1.5 | -157.6 | 6 | 8 |  |
| rc108C10 | medium | battery_infinite | -1133.3 | 4 | 9 |  |
| rc108C10 | medium | chargers_sparse_0.5 | -932.8 | 4 | 7 |  |
| rc108C10 | medium | charge_slow_x2 | -613.2 | 4 | 6 |  |
| rc108C10 | high | battery_tight_0.6 | 0.0 | 4 | 4 |  |
| rc108C10 | high | battery_nominal_1.0 | -370.3 | 1 | 7 |  |
| rc108C10 | high | battery_generous_1.5 | -960.2 | 3 | 7 |  |
| rc108C10 | high | battery_infinite | -2094.4 | 2 | 8 |  |
| rc108C10 | high | chargers_sparse_0.5 | -1003.1 | 3 | 7 |  |
| rc108C10 | high | charge_slow_x2 | -654.7 | 3 | 6 |  |
| c106C15 | low | battery_tight_0.6 | -225.3 | 11 | 12 |  |
| c106C15 | low | battery_nominal_1.0 | -2405.1 | 2 | 14 |  |
| c106C15 | low | battery_generous_1.5 | 1732.3 | 3 | 2 |  |
| c106C15 | low | battery_infinite | -2436.2 | 3 | 15 |  |
| c106C15 | low | chargers_sparse_0.5 | -622.7 | 8 | 14 |  |
| c106C15 | low | charge_slow_x2 | 272.0 | 2 | 2 |  |
| c106C15 | medium | battery_tight_0.6 | -220.3 | 8 | 10 |  |
| c106C15 | medium | battery_nominal_1.0 | 1929.0 | 10 | 1 |  |
| c106C15 | medium | battery_generous_1.5 | -1900.2 | 1 | 14 |  |
| c106C15 | medium | battery_infinite | -797.9 | 9 | 15 |  |
| c106C15 | medium | chargers_sparse_0.5 | 3669.5 | 10 | 2 |  |
| c106C15 | medium | charge_slow_x2 | -144.1 | 9 | 11 |  |
| c106C15 | high | battery_tight_0.6 | -357.9 | 6 | 10 |  |
| c106C15 | high | battery_nominal_1.0 | -500.0 | 1 | 1 |  |
| c106C15 | high | battery_generous_1.5 | -2645.5 | 1 | 14 |  |
| c106C15 | high | battery_infinite | -2828.4 | 1 | 15 |  |
| c106C15 | high | chargers_sparse_0.5 | -2472.9 | 1 | 14 |  |
| c106C15 | high | charge_slow_x2 | -2190.8 | 0 | 12 |  |

## 3. Computation–performance frontier

| Stem | Budget | Δ econ | CSS p50 | CSS p99 | Overruns | Loss |
|---|---:|---:|---:|---:|---:|---:|
| r103C10 | 0.15 | -167.6 | 0.120 | 0.143 | 0 | 0 |
| r103C10 | 0.35 | -1669.6 | 0.133 | 0.283 | 0 | 17 |
| r103C10 | 0.70 | -1669.6 | 0.140 | 0.526 | 0 | 17 |
| r103C10 | 1.50 | -1669.6 | 0.131 | 0.875 | 0 | 17 |
| c106C15 | 0.15 | 1428.5 | 0.128 | 0.395 | 29 | 3 |
| c106C15 | 0.35 | 1929.0 | 0.156 | 0.387 | 3 | 4 |
| c106C15 | 0.70 | -4209.9 | 0.014 | 0.562 | 0 | 40 |
| c106C15 | 1.50 | -4246.6 | 0.011 | 1.020 | 0 | 40 |
| rc108C5 | 0.15 | 93.7 | 0.020 | 0.124 | 0 | 0 |
| rc108C5 | 0.35 | 93.7 | 0.021 | 0.115 | 0 | 0 |
| rc108C5 | 0.70 | 93.7 | 0.020 | 0.113 | 0 | 0 |
| rc108C5 | 1.50 | 93.7 | 0.021 | 0.112 | 0 | 0 |

## 4. Large-instance probe (100 customers)

```json
[
  {
    "stem": "c101_21",
    "n_customers": 100,
    "fleet_size": 20,
    "wall_seconds": 1142.8971817999845,
    "css": {
      "completed": 4,
      "au": 0,
      "distance": 260.38922362047174,
      "economic": 139.61077637952826,
      "replay_ok": true,
      "n_decisions": 147,
      "fallback_count": 141
    },
    "gn": {
      "completed": 1,
      "au": 17,
      "distance": 353.1403293780741,
      "economic": -4503.140329378074,
      "replay_ok": true,
      "n_decisions": 153,
      "fallback_count": 137
    },
    "delta_economic": 4642.751105757602,
    "css_latency": {
      "n": 147,
      "p50": 3.35551799996756,
      "p95": 8.858168700011447,
      "p99": 14.808192899974529,
      "max": 20.625284900015686,
      "mean": 4.244097125850345,
      "frac_over_budget": 0.9523809523809523
    },
    "loss_events": 0,
    "failure": null
  },
  {
    "stem": "r101_21",
    "n_customers": 100,
    "fleet_size": 20,
    "wall_seconds": 571.5659952000133,
    "css": {
      "completed": 4,
      "au": 0,
      "distance": 200.5904318108187,
      "economic": 199.4095681891813,
      "replay_ok": true,
      "n_decisions": 143,
      "fallback_count": 137
    },
    "gn": {
      "completed": 0,
      "au": 22,
      "distance": 481.01372323739724,
      "economic": -5981.013723237397,
      "replay_ok": true,
      "n_decisions": 155,
      "fallback_count": 91
    },
    "delta_economic": 6180.4232914265785,
    "css_latency": {
      "n": 143,
      "p50": 3.208210499957204,
      "p95": 7.859291800006758,
      "p99": 12.726150200003758,
      "max": 18.550811900000554,
      "mean": 3.8508135405563673,
      "frac_over_budget": 0.9370629370629371
    },
    "loss_events": 0,
    "failure": null
  },
  {
    "stem": "rc101_21",
    "n_customers": 100,
    "fleet_size": 20,
    "wall_seconds": 1236.3572920999723,
    "css": {
      "completed": 2,
      "au": 0,
      "distance": 143.20994951559993,
      "economic": 56.79005048440007,
      "replay_ok": true,
      "n_decisions": 140,
      "fallback_count": 135
    },
    "gn": {
      "completed": 15,
      "au": 0,
      "distance": 1047.3734368306039,
      "economic": 452.62656316939615,
      "replay_ok": true,
      "n_decisions": 185,
      "fallback_count": 170
    },
    "delta_economic": -395.8365126849961,
    "css_latency": {
      "n": 140,
      "p50": 2.899461400054861,
      "p95": 8.677213500021026,
      "p99": 9.59979890001705,
      "max": 13.45896580000408,
      "mean": 3.8219218992852673,
      "frac_over_budget": 0.9357142857142857
    },
    "loss_events": 0,
    "failure": null
  }
]
```

## Reading

EV regimes: 54 cells, 0 failures, CSS better 17 / worse 35. Divergence labels document charge-vs-service and hindsight agreement. Budget frontier reports cooperative overruns without redefining the objective. Large stems are a credibility probe, not a confirmatory claim.
