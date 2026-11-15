# MPC development comparison

**Gate:** `FAIL` — CSS-MPC loses substantially to greedy-nominal on completed (mean_delta=-1.0, tally={'better': 7, 'worse': 8, 'tie': 3}; means css=4.5, gn=5.5). Economic mean_delta=-6.7371700657327835, tally={'better': 11, 'worse': 7, 'tie': 0}.

Approximation class: `restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse`

Budget: 0.35s cooperative wall; scenarios=2.

## Mean completed / economic (valid replays only)

```json
{
  "b1": {
    "completed": {
      "n": 18,
      "mean": 3.3333333333333335,
      "std": 3.2719844670996188
    },
    "economic": {
      "n": 18,
      "mean": -645.3594003594463,
      "std": 1124.7679062931704
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 0,
    "mean_decide_latency_across_episodes": {
      "n": 0,
      "mean": null
    }
  },
  "m1": {
    "completed": {
      "n": 18,
      "mean": 4.444444444444445,
      "std": 3.3819977079726153
    },
    "economic": {
      "n": 18,
      "mean": -179.4239368559494,
      "std": 734.9479988277184
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 0,
    "mean_decide_latency_across_episodes": {
      "n": 0,
      "mean": null
    }
  },
  "cce_greedy_nominal": {
    "completed": {
      "n": 18,
      "mean": 5.5,
      "std": 3.929526239966879
    },
    "economic": {
      "n": 18,
      "mean": 155.9728193090301,
      "std": 580.1771897950995
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 13,
    "mean_decide_latency_across_episodes": {
      "n": 0,
      "mean": null
    }
  },
  "stochastic_cce_causal": {
    "completed": {
      "n": 18,
      "mean": 5.444444444444445,
      "std": 2.748737083745107
    },
    "economic": {
      "n": 18,
      "mean": 260.2471007659586,
      "std": 396.23752627451546
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 238,
    "mean_decide_latency_across_episodes": {
      "n": 0,
      "mean": null
    }
  },
  "commitment_safe_stochastic_mpc": {
    "completed": {
      "n": 18,
      "mean": 4.5,
      "std": 2.455486054675506
    },
    "economic": {
      "n": 18,
      "mean": 149.23564924329727,
      "std": 426.84162443315626
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 273,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.16005378096618292,
      "std": 0.09160605978416578
    }
  },
  "css_mpc_no_forecast": {
    "completed": {
      "n": 18,
      "mean": 4.111111111111111,
      "std": 1.9369135207665067
    },
    "economic": {
      "n": 18,
      "mean": -63.672993639914516,
      "std": 509.52596181646504
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 215,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.1298215010793733,
      "std": 0.08512248882892028
    }
  },
  "css_mpc_no_terminal": {
    "completed": {
      "n": 18,
      "mean": 5.055555555555555,
      "std": 2.732639797235982
    },
    "economic": {
      "n": 18,
      "mean": 89.8191602654801,
      "std": 710.5656223325047
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 235,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.14958982492867867,
      "std": 0.08763224796169061
    }
  }
}
```

## Paired CSS-MPC vs baselines

```json
{
  "css_vs_gn_completed": {
    "delta": {
      "n": 18,
      "mean": -1.0,
      "std": 4.311407576896164
    },
    "tally": {
      "better": 7,
      "worse": 8,
      "tie": 3
    },
    "metric": "completed_count"
  },
  "css_vs_gn_economic": {
    "delta": {
      "n": 18,
      "mean": -6.7371700657327835,
      "std": 832.3123996894086
    },
    "tally": {
      "better": 11,
      "worse": 7,
      "tie": 0
    },
    "metric": "economic_objective"
  },
  "css_vs_stochastic_cce": {
    "delta": {
      "n": 18,
      "mean": -0.9444444444444444,
      "std": 2.732639797235982
    },
    "tally": {
      "better": 2,
      "worse": 5,
      "tie": 11
    },
    "metric": "completed_count"
  },
  "css_vs_m1": {
    "delta": {
      "n": 18,
      "mean": 0.05555555555555555,
      "std": 4.0940735103923975
    },
    "tally": {
      "better": 10,
      "worse": 4,
      "tie": 4
    },
    "metric": "completed_count"
  },
  "css_vs_b1": {
    "delta": {
      "n": 18,
      "mean": 1.1666666666666667,
      "std": 3.5355339059327373
    },
    "tally": {
      "better": 10,
      "worse": 5,
      "tie": 3
    },
    "metric": "completed_count"
  },
  "css_vs_no_forecast": {
    "delta": {
      "n": 18,
      "mean": 0.3888888888888889,
      "std": 1.2897281468629185
    },
    "tally": {
      "better": 8,
      "worse": 3,
      "tie": 7
    },
    "metric": "completed_count"
  },
  "css_vs_no_terminal": {
    "delta": {
      "n": 18,
      "mean": -0.5555555555555556,
      "std": 2.5022865360499247
    },
    "tally": {
      "better": 3,
      "worse": 5,
      "tie": 10
    },
    "metric": "completed_count"
  }
}
```

## Infinite-battery (rebuilt arcs)

```json
{
  "cce_greedy_nominal": {
    "completed": {
      "n": 3,
      "mean": 9.333333333333334,
      "std": 6.027713773341708
    },
    "economic": {
      "n": 3,
      "mean": 592.6824906614252,
      "std": 484.02950184098023
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 1,
    "mean_decide_latency_across_episodes": {
      "n": 0,
      "mean": null
    }
  },
  "commitment_safe_stochastic_mpc": {
    "completed": {
      "n": 3,
      "mean": 7.0,
      "std": 3.4641016151377544
    },
    "economic": {
      "n": 3,
      "mean": 324.6984657699172,
      "std": 213.0806191400117
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 55,
    "mean_decide_latency_across_episodes": {
      "n": 3,
      "mean": 0.17793404008507918,
      "std": 0.15637544761423022
    }
  }
}
```

Reproduce: `python -m safe_time_evrp.mpc_central.mpc_development_eval`
