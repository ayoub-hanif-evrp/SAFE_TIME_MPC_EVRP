# Final competitive comparison

**Archived baseline SHA:** `442a42329d283bad14f1900eac6a37ab33b6e0cb`
**Protocol:** `2026-11-14.v2`
**Wall seconds:** 1657.8021861999878

## Decision

**greedy_nominal_remains_strongest_empirical_contribution**

Final held-out BAP did not beat greedy-nominal (delta~-2.167, tally={'better': 1, 'worse': 2, 'tie': 3}). Recommend nominal CC-E as strongest empirical result; predictive superiority not shown.

## Development completed means

```json
{
  "b1": {
    "n": 18,
    "mean": 4.444444444444445,
    "std": 3.9440531887330774
  },
  "m1": {
    "n": 18,
    "mean": 4.888888888888889,
    "std": 3.512815008087638
  },
  "cce_greedy_nominal": {
    "n": 18,
    "mean": 6.166666666666667,
    "std": 3.6662210067845384
  },
  "cce_causal_empty_future": {
    "n": 18,
    "mean": 4.166666666666667,
    "std": 2.5495097567963922
  },
  "cce_conditional_poisson": {
    "n": 18,
    "mean": 3.388888888888889,
    "std": 1.9745107774984456
  },
  "cce_finite_demand": {
    "n": 18,
    "mean": 4.166666666666667,
    "std": 2.5495097567963922
  },
  "bap_cce": {
    "n": 18,
    "mean": 3.5555555555555554,
    "std": 3.4166068861341197
  },
  "stochastic_finite": {
    "n": 18,
    "mean": 3.6666666666666665,
    "std": 3.105971478222138
  }
}
```

## Paired vs greedy-nominal (development)

```json
{
  "completed_delta": {
    "n": 18,
    "mean": -2.611111111111111,
    "std": 4.2445659223625025
  },
  "tally": {
    "better": 1,
    "worse": 8,
    "tie": 9
  }
}
```

## Held-out final

```json
{
  "bap_vs_greedy_nominal": {
    "completed_delta": {
      "n": 6,
      "mean": -2.1666666666666665,
      "std": 5.344779384283945
    },
    "tally": {
      "better": 1,
      "worse": 2,
      "tie": 3
    }
  },
  "bap_vs_b1": {
    "completed_delta": {
      "n": 6,
      "mean": 0.16666666666666666,
      "std": 5.115336417740935
    },
    "tally": {
      "better": 1,
      "worse": 2,
      "tie": 3
    }
  }
}
```

## Limitations

Base Schneider instances appeared in earlier experiments; fresh environment seeds do not make them completely unseen instances. Cooperative time limits are not hard-preemptive for noninterruptible ALNS calls.

Reproduce: `python -m safe_time_evrp.mpc_central.competitive_predictive_eval`
