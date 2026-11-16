# Corrected MPC ablations

| Ablation | Controllers | Notes |
|---|---|---|
| Forecast | css vs no_forecast | Margin rule on forecast path |
| Terminal | css vs no_terminal | Stage-0 Validate retained |
| Anticipatory charging | css vs no_predictive_charge | Keep incumbent charge only |
| Warm init | css vs no_warm_init | Safety backup retained |
| Warm+backup removed | no_warm_no_backup | Not isolated warm-start |
| Battery | infinite_battery_rows | Rebuilt arcs; small n |

```json
{
  "css_vs_gn_economic_clustered": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 72.6196464589811,
      "std": 779.3073091004641,
      "median": -30.592053444693704
    },
    "tally_stems": {
      "better": 4,
      "worse": 5,
      "tie": 0
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 259.769103033488,
      "low": -526.4079051362423,
      "high": 671.6471980542044
    },
    "per_stem_mean_delta": {
      "c103C5": -38.388312797002584,
      "r105C5": 16.5339559641602,
      "rc108C5": 56.77532316140542,
      "c104C10": 694.8064527580821,
      "r103C10": -880.0429381704064,
      "rc108C10": -624.231611810586,
      "c106C15": 1775.6114015543974,
      "r105C15": -30.592053444693704,
      "rc108C15": -316.8953990845266
    }
  },
  "css_vs_gn_completed_clustered": {
    "metric": "completed_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -0.3888888888888889,
      "std": 2.98724138815582,
      "median": -1.0
    },
    "tally_stems": {
      "better": 3,
      "worse": 5,
      "tie": 1
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 0.9957471293852733,
      "low": -2.685081769251329,
      "high": 1.9073039914735515
    },
    "per_stem_mean_delta": {
      "c103C5": -1.0,
      "r105C5": 0.0,
      "rc108C5": 0.5,
      "c104C10": 2.5,
      "r103C10": -4.5,
      "rc108C10": -2.5,
      "c106C15": 5.5,
      "r105C15": -1.5,
      "rc108C15": -2.5
    }
  },
  "css_vs_gn_au_clustered": {
    "metric": "accepted_unfulfilled_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -0.2777777777777778,
      "std": 2.3063920838496745,
      "median": 0.0
    },
    "tally_stems": {
      "better": 3,
      "worse": 2,
      "tie": 4
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 0.7687973612832248,
      "low": -2.0506244928968944,
      "high": 1.4950689373413386
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": -2.0,
      "r103C10": 2.0,
      "rc108C10": 2.0,
      "c106C15": -5.5,
      "r105C15": 0.0,
      "rc108C15": 1.0
    }
  },
  "css_vs_stochastic_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 308.7905063705996,
      "std": 839.4149658679695,
      "median": 0.0
    },
    "tally_stems": {
      "better": 4,
      "worse": 4,
      "tie": 1
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 279.8049886226565,
      "low": -336.4397973932463,
      "high": 954.0208101344455
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": -47.52417796388046,
      "rc108C5": -0.5851900617775598,
      "c104C10": 79.50302850040529,
      "r103C10": -273.9455690168799,
      "rc108C10": -586.7705469074754,
      "c106C15": 2197.537794169132,
      "r105C15": 357.10499511248486,
      "rc108C15": 1053.7942235033872
    }
  },
  "css_vs_no_forecast_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -2.909641397385028,
      "std": 201.0908996233765,
      "median": 0.0
    },
    "tally_stems": {
      "better": 4,
      "worse": 3,
      "tie": 2
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 67.03029987445883,
      "low": -157.4815129078871,
      "high": 151.66223011311703
    },
    "per_stem_mean_delta": {
      "c103C5": -20.301650494947154,
      "r105C5": 0.0,
      "rc108C5": 56.77532316140542,
      "c104C10": 225.866174678481,
      "r103C10": 0.0,
      "rc108C10": -132.7925678801776,
      "c106C15": -446.2400284269795,
      "r105C15": 74.6676497760721,
      "rc108C15": 215.83832660968048
    }
  },
  "css_vs_no_terminal_au": {
    "metric": "accepted_unfulfilled_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -0.8333333333333334,
      "std": 1.620185174601965,
      "median": 0.0
    },
    "tally_stems": {
      "better": 0,
      "worse": 4,
      "tie": 5
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 0.5400617248673217,
      "low": -2.0787156708773775,
      "high": 0.41204900421071067
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": 0.0,
      "r103C10": 0.0,
      "rc108C10": -0.5,
      "c106C15": -5.0,
      "r105C15": -1.0,
      "rc108C15": -1.0
    }
  },
  "css_vs_no_predictive_charge_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 141.74473824385777,
      "std": 496.3445074610791,
      "median": -14.020791176284817
    },
    "tally_stems": {
      "better": 4,
      "worse": 5,
      "tie": 0
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 165.44816915369304,
      "low": -239.77873982455841,
      "high": 523.2682163122739
    },
    "per_stem_mean_delta": {
      "c103C5": 11.423561628526485,
      "r105C5": -25.294213107512434,
      "rc108C5": -14.020791176284817,
      "c104C10": 377.6199119625402,
      "r103C10": 118.21596692801353,
      "rc108C10": -51.354360255890754,
      "c106C15": -441.2048344736198,
      "r105C15": 1339.8821088112045,
      "rc108C15": -39.564706122257064
    }
  },
  "css_vs_no_warm_init_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 588.1283453497833,
      "std": 735.5135815328177,
      "median": 120.20886899958877
    },
    "tally_stems": {
      "better": 5,
      "worse": 1,
      "tie": 3
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 245.17119384427258,
      "low": 22.763572344890804,
      "high": 1153.493118354676
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": 1159.8572948357166,
      "r103C10": 120.20886899958877,
      "rc108C10": 1074.8455496696677,
      "c106C15": -9.545575200626672,
      "r105C15": 2012.9043590439499,
      "rc108C15": 934.8846107997538
    }
  }
}
```
