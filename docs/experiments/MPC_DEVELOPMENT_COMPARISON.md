# MPC development comparison

**Gate:** `FAIL` — CSS-MPC loses substantially to greedy-nominal on completed (mean_delta=-0.7222222222222222, tally={'better': 7, 'worse': 8, 'tie': 3}, ci95={'level': 0.95, 'method': 'paired_student_t', 'df': 17, 'se': 1.0187957634151465, 'low': -2.8718812830281815, 'high': 1.4274368385837368}; means css=4.055555555555555, gn=4.777777777777778). Economic mean_delta=155.8270764726209, tally={'better': 11, 'worse': 7, 'tie': 0}, ci95={'level': 0.95, 'method': 'paired_student_t', 'df': 17, 'se': 208.72730213770046, 'low': -284.5875310379271, 'high': 596.2416839831689}.

Protocol: `mpc_development_v2_full_ablations`

Approximation class: `restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse`

Budget: 0.35s cooperative wall; scenarios=2.

## Ablation matrix

```json
{
  "forecast": "commitment_safe_stochastic_mpc vs css_mpc_no_forecast",
  "terminal": "commitment_safe_stochastic_mpc vs css_mpc_no_terminal",
  "anticipatory_charging": "commitment_safe_stochastic_mpc vs css_mpc_no_charge",
  "horizon": "css_mpc_short_horizon vs css_mpc_long_horizon",
  "warm_start": "commitment_safe_stochastic_mpc vs css_mpc_no_warm_start",
  "battery": "infinite_battery_summary"
}
```

## Mean metrics (valid replays only)

```json
{
  "b1": {
    "completed": {
      "n": 18,
      "mean": 3.7222222222222223,
      "std": 3.8776213987982766
    },
    "economic": {
      "n": 18,
      "mean": -535.0051926322308,
      "std": 1130.051069855924
    },
    "distance": {
      "n": 18,
      "mean": 171.11630374334183,
      "std": 122.05133529498511
    },
    "charge_time": {
      "n": 18,
      "mean": 190.22712739088203,
      "std": 327.2947295377808
    },
    "charge_energy": {
      "n": 18,
      "mean": 88.74460015042115,
      "std": 94.12447488965816
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 2.9444444444444446,
      "std": 3.8725614296152604
    },
    "rejected": {
      "n": 18,
      "mean": 3.0,
      "std": 2.3763541031440183
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 50,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.04219809537152061,
      "std": 0.03802807529837997
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.04219809537152061,
      "median": 0.03697929828854671,
      "p95": 0.0900744999967644,
      "p99": 0.0900744999967644,
      "max": 0.12773891538471127,
      "frac_over_budget": 0.0
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
      "mean": -181.12349673228792,
      "std": 732.3299953644471
    },
    "distance": {
      "n": 18,
      "mean": 195.0123856211768,
      "std": 115.0196955516682
    },
    "charge_time": {
      "n": 18,
      "mean": 214.09398861550528,
      "std": 330.0398392863763
    },
    "charge_energy": {
      "n": 18,
      "mean": 110.89339912093936,
      "std": 87.5124094290123
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 1.7222222222222223,
      "std": 2.5159621140782553
    },
    "rejected": {
      "n": 18,
      "mean": 3.8333333333333335,
      "std": 2.3072774891123746
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 23,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.03903262365688349,
      "std": 0.033709920737241564
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.03903262365688349,
      "median": 0.032806909637769686,
      "p95": 0.09482289411500781,
      "p99": 0.09482289411500781,
      "max": 0.0977649268312323,
      "frac_over_budget": 0.0
    }
  },
  "cce_greedy_nominal": {
    "completed": {
      "n": 18,
      "mean": 4.777777777777778,
      "std": 3.540614030421602
    },
    "economic": {
      "n": 18,
      "mean": -22.917608306550925,
      "std": 785.5591916982653
    },
    "distance": {
      "n": 18,
      "mean": 209.02871941766205,
      "std": 129.72059662755382
    },
    "charge_time": {
      "n": 18,
      "mean": 147.3364843865708,
      "std": 224.39262516602412
    },
    "charge_energy": {
      "n": 18,
      "mean": 141.25853071786585,
      "std": 104.28692083267764
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 1.1666666666666667,
      "std": 2.50293944839921
    },
    "rejected": {
      "n": 18,
      "mean": 2.888888888888889,
      "std": 2.654383475307765
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 9,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.04798406671628374,
      "std": 0.035100789329658225
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.04798406671628374,
      "median": 0.044585178450198736,
      "p95": 0.10077872142677993,
      "p99": 0.10077872142677993,
      "max": 0.10285095571640081,
      "frac_over_budget": 0.0
    }
  },
  "stochastic_cce_causal": {
    "completed": {
      "n": 18,
      "mean": 4.722222222222222,
      "std": 2.6525360906910014
    },
    "economic": {
      "n": 18,
      "mean": -56.02666614730507,
      "std": 838.4499238211663
    },
    "distance": {
      "n": 18,
      "mean": 181.02666614730504,
      "std": 88.12386807460082
    },
    "charge_time": {
      "n": 18,
      "mean": 220.060144330065,
      "std": 278.76831864324237
    },
    "charge_energy": {
      "n": 18,
      "mean": 127.73861011064118,
      "std": 59.12861086226512
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 1.3888888888888888,
      "std": 2.8929709721584893
    },
    "rejected": {
      "n": 18,
      "mean": 3.7777777777777777,
      "std": 2.556549962824568
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 204,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.13727616379439056,
      "std": 0.0833510964054009
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.13727616379439056,
      "median": 0.1213060067617264,
      "p95": 0.27220569253263216,
      "p99": 0.27220569253263216,
      "max": 0.3201037890630687,
      "frac_over_budget": 0.0
    }
  },
  "commitment_safe_stochastic_mpc": {
    "completed": {
      "n": 18,
      "mean": 4.055555555555555,
      "std": 2.5546318307829945
    },
    "economic": {
      "n": 18,
      "mean": 132.90946816606993,
      "std": 386.5659585495111
    },
    "distance": {
      "n": 18,
      "mean": 161.5349762783745,
      "std": 80.11081582114437
    },
    "charge_time": {
      "n": 18,
      "mean": 173.84999726931602,
      "std": 220.03372994876312
    },
    "charge_energy": {
      "n": 18,
      "mean": 99.86659492904295,
      "std": 53.8556689863474
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 0.4444444444444444,
      "std": 1.0966377611066325
    },
    "rejected": {
      "n": 18,
      "mean": 4.166666666666667,
      "std": 3.6662210067845384
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 220,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.13578806274496535,
      "std": 0.07799593029104508
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.13578806274496535,
      "median": 0.11526204584004077,
      "p95": 0.2685873540944695,
      "p99": 0.2685873540944695,
      "max": 0.30798139500257093,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_no_forecast": {
    "completed": {
      "n": 18,
      "mean": 4.722222222222222,
      "std": 2.6078062801464457
    },
    "economic": {
      "n": 18,
      "mean": 187.3012627929767,
      "std": 357.03369215703646
    },
    "distance": {
      "n": 18,
      "mean": 187.6987372070233,
      "std": 89.9746909007628
    },
    "charge_time": {
      "n": 18,
      "mean": 197.29818411425816,
      "std": 236.95944973187383
    },
    "charge_energy": {
      "n": 18,
      "mean": 127.25022876943343,
      "std": 47.53448592040108
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 0.3888888888888889,
      "std": 1.1447521637192346
    },
    "rejected": {
      "n": 18,
      "mean": 4.833333333333333,
      "std": 3.434256491157704
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 184,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.11821933524819407,
      "std": 0.07364227978126212
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.11821933524819407,
      "median": 0.13435427946595674,
      "p95": 0.23073008955359015,
      "p99": 0.23073008955359015,
      "max": 0.24906156428603157,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_no_terminal": {
    "completed": {
      "n": 18,
      "mean": 4.666666666666667,
      "std": 2.807552838536876
    },
    "economic": {
      "n": 18,
      "mean": -131.8913999712685,
      "std": 1017.0295206013642
    },
    "distance": {
      "n": 18,
      "mean": 181.8913999712685,
      "std": 91.24778260308746
    },
    "charge_time": {
      "n": 18,
      "mean": 199.4667569094944,
      "std": 274.93897158356424
    },
    "charge_energy": {
      "n": 18,
      "mean": 131.19892546244938,
      "std": 70.29788396861682
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 1.6666666666666667,
      "std": 3.5313720046596786
    },
    "rejected": {
      "n": 18,
      "mean": 3.5555555555555554,
      "std": 2.3319323525205498
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 184,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.12831325394497403,
      "std": 0.06792904904570995
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.12831325394497403,
      "median": 0.11744371818092847,
      "p95": 0.23735855156155594,
      "p99": 0.23735855156155594,
      "max": 0.25264502985145787,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_no_charge": {
    "completed": {
      "n": 18,
      "mean": 3.2222222222222223,
      "std": 2.1843172457464504
    },
    "economic": {
      "n": 18,
      "mean": -55.61265366305411,
      "std": 680.9407510516944
    },
    "distance": {
      "n": 18,
      "mean": 155.6126536630541,
      "std": 97.79303584706146
    },
    "charge_time": {
      "n": 18,
      "mean": 116.67835679000652,
      "std": 272.197943117357
    },
    "charge_energy": {
      "n": 18,
      "mean": 50.97209295742873,
      "std": 76.74527502710494
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 0.8888888888888888,
      "std": 2.2980525998405663
    },
    "rejected": {
      "n": 18,
      "mean": 5.166666666666667,
      "std": 3.3998269852173015
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 237,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.16009078759608358,
      "std": 0.09820743800403223
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.16009078759608358,
      "median": 0.12987848853389827,
      "p95": 0.31206484807905954,
      "p99": 0.31206484807905954,
      "max": 0.31866839166517213,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_short_horizon": {
    "completed": {
      "n": 18,
      "mean": 4.388888888888889,
      "std": 2.872565749800708
    },
    "economic": {
      "n": 18,
      "mean": 219.63273592141078,
      "std": 301.5163327422894
    },
    "distance": {
      "n": 18,
      "mean": 177.58948630081144,
      "std": 114.32276852574326
    },
    "charge_time": {
      "n": 18,
      "mean": 171.1581743176727,
      "std": 242.77781106831432
    },
    "charge_energy": {
      "n": 18,
      "mean": 107.4175575329327,
      "std": 61.57370025621887
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 0.16666666666666666,
      "std": 0.7071067811865476
    },
    "rejected": {
      "n": 18,
      "mean": 5.444444444444445,
      "std": 3.2938842120837184
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 149,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.10948942576915807,
      "std": 0.06624370990377627
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.10948942576915807,
      "median": 0.10646462843930288,
      "p95": 0.19575683571581196,
      "p99": 0.19575683571581196,
      "max": 0.27549352968344465,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_long_horizon": {
    "completed": {
      "n": 18,
      "mean": 4.111111111111111,
      "std": 2.348688968186517
    },
    "economic": {
      "n": 18,
      "mean": 143.95857965743485,
      "std": 376.2776569931472
    },
    "distance": {
      "n": 18,
      "mean": 169.93030923145403,
      "std": 81.79446549002122
    },
    "charge_time": {
      "n": 18,
      "mean": 186.9897272901004,
      "std": 270.13757207836824
    },
    "charge_energy": {
      "n": 18,
      "mean": 110.53205652741742,
      "std": 63.56316244822852
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 0.3888888888888889,
      "std": 1.2432826042324119
    },
    "rejected": {
      "n": 18,
      "mean": 4.833333333333333,
      "std": 4.259936481161358
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 303,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.16200930116163043,
      "std": 0.08132552433101298
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.16200930116163043,
      "median": 0.14066937411893907,
      "p95": 0.2696325107683571,
      "p99": 0.2696325107683571,
      "max": 0.3025551344273749,
      "frac_over_budget": 0.0
    }
  },
  "css_mpc_no_warm_start": {
    "completed": {
      "n": 18,
      "mean": 2.111111111111111,
      "std": 1.5296631266542813
    },
    "economic": {
      "n": 18,
      "mean": -266.1371462645385,
      "std": 636.9187132727476
    },
    "distance": {
      "n": 18,
      "mean": 88.3593684867607,
      "std": 39.528695205290994
    },
    "charge_time": {
      "n": 18,
      "mean": 94.93454270231972,
      "std": 143.33323194199423
    },
    "charge_energy": {
      "n": 18,
      "mean": 46.649219145809774,
      "std": 43.89323756448927
    },
    "accepted_unfulfilled": {
      "n": 18,
      "mean": 1.5555555555555556,
      "std": 2.2549872106647166
    },
    "rejected": {
      "n": 18,
      "mean": 4.666666666666667,
      "std": 3.7729688731351945
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 159,
    "mean_decide_latency_across_episodes": {
      "n": 18,
      "mean": 0.11824250873504624,
      "std": 0.07313626294207855
    },
    "latency_percentiles_across_episode_means": {
      "n": 18,
      "mean": 0.11824250873504624,
      "median": 0.11311688421476308,
      "p95": 0.20654069999559746,
      "p99": 0.20654069999559746,
      "max": 0.29059711296361423,
      "frac_over_budget": 0.0
    }
  }
}
```

## Paired differences with 95% Student-t CIs

```json
{
  "css_vs_gn_completed": {
    "delta": {
      "n": 18,
      "mean": -0.7222222222222222,
      "std": 4.322384357729853
    },
    "tally": {
      "better": 7,
      "worse": 8,
      "tie": 3
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 1.0187957634151465,
      "low": -2.8718812830281815,
      "high": 1.4274368385837368
    }
  },
  "css_vs_gn_economic": {
    "delta": {
      "n": 18,
      "mean": 155.8270764726209,
      "std": 885.554944562048
    },
    "tally": {
      "better": 11,
      "worse": 7,
      "tie": 0
    },
    "metric": "economic_objective",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 208.72730213770046,
      "low": -284.5875310379271,
      "high": 596.2416839831689
    }
  },
  "css_vs_stochastic_cce": {
    "delta": {
      "n": 18,
      "mean": -0.6666666666666666,
      "std": 2.42535625036333
    },
    "tally": {
      "better": 2,
      "worse": 4,
      "tie": 12
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.5716619504750295,
      "low": -1.872873382168979,
      "high": 0.5395400488356455
    }
  },
  "css_vs_m1": {
    "delta": {
      "n": 18,
      "mean": -0.3888888888888889,
      "std": 4.0020419624587955
    },
    "tally": {
      "better": 8,
      "worse": 6,
      "tie": 4
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.9432903367492443,
      "low": -2.3792314994297943,
      "high": 1.6014537216520166
    }
  },
  "css_vs_b1": {
    "delta": {
      "n": 18,
      "mean": 0.3333333333333333,
      "std": 4.325029751682776
    },
    "tally": {
      "better": 8,
      "worse": 5,
      "tie": 5
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 1.019419288749487,
      "low": -1.8176413659280841,
      "high": 2.484308032594751
    }
  },
  "css_vs_no_forecast": {
    "delta": {
      "n": 18,
      "mean": -0.6666666666666666,
      "std": 2.765331593774861
    },
    "tally": {
      "better": 6,
      "worse": 7,
      "tie": 5
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.6517949073958692,
      "low": -2.0419539212719506,
      "high": 0.7086205879386173
    }
  },
  "css_vs_no_terminal": {
    "delta": {
      "n": 18,
      "mean": -0.6111111111111112,
      "std": 2.3298293017222096
    },
    "tally": {
      "better": 2,
      "worse": 3,
      "tie": 13
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.5491460327516311,
      "low": -1.7698092402170527,
      "high": 0.5475870179948303
    }
  },
  "css_vs_no_charge": {
    "delta": {
      "n": 18,
      "mean": 0.8333333333333334,
      "std": 2.3326329481056884
    },
    "tally": {
      "better": 7,
      "worse": 3,
      "tie": 8
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.5498068585415669,
      "low": -0.3267591381893725,
      "high": 1.9934258048560394
    }
  },
  "css_short_vs_long": {
    "delta": {
      "n": 18,
      "mean": 0.2777777777777778,
      "std": 4.026464739775277
    },
    "tally": {
      "better": 6,
      "worse": 8,
      "tie": 4
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.9490468405678755,
      "low": -1.7247110558204395,
      "high": 2.280266611375995
    }
  },
  "css_vs_no_warm_start": {
    "delta": {
      "n": 18,
      "mean": 1.9444444444444444,
      "std": 2.5081566285227512
    },
    "tally": {
      "better": 9,
      "worse": 0,
      "tie": 9
    },
    "metric": "completed_count",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 0.5911781867688086,
      "low": 0.6970584703622582,
      "high": 3.1918304185266306
    }
  },
  "css_vs_gn_charge_time": {
    "delta": {
      "n": 18,
      "mean": 26.513512882745218,
      "std": 205.3731973310368
    },
    "tally": {
      "better": 6,
      "worse": 12,
      "tie": 0
    },
    "metric": "charge_time",
    "ci95": {
      "level": 0.95,
      "method": "paired_student_t",
      "df": 17,
      "se": 48.4069268355797,
      "low": -75.62510274032795,
      "high": 128.65212850581838
    }
  }
}
```

## Infinite-battery (rebuilt arcs)

```json
{
  "cce_greedy_nominal": {
    "completed": {
      "n": 3,
      "mean": 4.666666666666667,
      "std": 4.725815626252609
    },
    "economic": {
      "n": 3,
      "mean": -507.14709571055954,
      "std": 1542.2401207761159
    },
    "distance": {
      "n": 3,
      "mean": 223.81376237722623,
      "std": 119.2347871804401
    },
    "charge_time": {
      "n": 3,
      "mean": 0.0,
      "std": 0.0
    },
    "charge_energy": {
      "n": 3,
      "mean": 0.0,
      "std": 0.0
    },
    "accepted_unfulfilled": {
      "n": 3,
      "mean": 3.0,
      "std": 5.196152422706632
    },
    "rejected": {
      "n": 3,
      "mean": 0.6666666666666666,
      "std": 1.1547005383792517
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 12,
    "mean_decide_latency_across_episodes": {
      "n": 3,
      "mean": 0.07584860066852388,
      "std": 0.05638992405086274
    },
    "latency_percentiles_across_episode_means": {
      "n": 3,
      "mean": 0.07584860066852388,
      "median": 0.06276220847532879,
      "p95": 0.06276220847532879,
      "p99": 0.06276220847532879,
      "max": 0.13763112414142534,
      "frac_over_budget": 0.0
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
      "mean": 456.6659965170181,
      "std": 258.11038395136427
    },
    "distance": {
      "n": 3,
      "mean": 243.3340034829819,
      "std": 101.88167978407064
    },
    "charge_time": {
      "n": 3,
      "mean": 0.0,
      "std": 0.0
    },
    "charge_energy": {
      "n": 3,
      "mean": 0.0,
      "std": 0.0
    },
    "accepted_unfulfilled": {
      "n": 3,
      "mean": 0.0,
      "std": 0.0
    },
    "rejected": {
      "n": 3,
      "mean": 3.0,
      "std": 2.6457513110645907
    },
    "replay_failures": 0,
    "deadline_overruns_sum": 55,
    "mean_decide_latency_across_episodes": {
      "n": 3,
      "mean": 0.1952164635278084,
      "std": 0.17318390488662677
    },
    "latency_percentiles_across_episode_means": {
      "n": 3,
      "mean": 0.1952164635278084,
      "median": 0.12861964915448926,
      "p95": 0.12861964915448926,
      "p99": 0.12861964915448926,
      "max": 0.39181310447183115,
      "frac_over_budget": 0.3333333333333333
    }
  }
}
```

Reproduce: `python -m safe_time_evrp.mpc_central.mpc_development_eval`
