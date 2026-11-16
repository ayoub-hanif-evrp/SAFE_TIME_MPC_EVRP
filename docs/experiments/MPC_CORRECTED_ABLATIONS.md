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
      "mean": 145.16217966006948,
      "std": 552.1791146580938,
      "median": 70.79611433769023
    },
    "tally_stems": {
      "better": 7,
      "worse": 2,
      "tie": 0
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 184.05970488603126,
      "low": -279.27949980711855,
      "high": 569.6038591272576
    },
    "per_stem_mean_delta": {
      "c103C5": -17.15715079168757,
      "r105C5": 41.82816907167263,
      "rc108C5": 70.79611433769023,
      "c104C10": 498.8821123678921,
      "r103C10": 8.268784492268196,
      "rc108C10": -925.1109875453873,
      "c106C15": 1166.073359041286,
      "r105C15": 73.0588444332009,
      "rc108C15": 389.82037153369026
    }
  },
  "css_vs_gn_completed_clustered": {
    "metric": "completed_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -0.3888888888888889,
      "std": 1.90029237516523,
      "median": -0.5
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
      "se": 0.6334307917217433,
      "low": -1.849580294599229,
      "high": 1.0718025168214513
    },
    "per_stem_mean_delta": {
      "c103C5": -0.5,
      "r105C5": 0.5,
      "rc108C5": 0.5,
      "c104C10": -1.0,
      "r103C10": 0.0,
      "rc108C10": -3.0,
      "c106C15": 3.5,
      "r105C15": -1.0,
      "rc108C15": -2.5
    }
  },
  "css_vs_gn_au_clustered": {
    "metric": "accepted_unfulfilled_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -0.6111111111111112,
      "std": 1.9329022507905336,
      "median": 0.0
    },
    "tally_stems": {
      "better": 1,
      "worse": 4,
      "tie": 4
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 0.6443007502635112,
      "low": -2.096868641218768,
      "high": 0.8746464189965457
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": -2.0,
      "r103C10": 0.0,
      "rc108C10": 3.0,
      "c106C15": -4.0,
      "r105C15": -0.5,
      "rc108C15": -2.0
    }
  },
  "css_vs_stochastic_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -242.03201534261993,
      "std": 499.44713504160825,
      "median": -116.42131188978462
    },
    "tally_stems": {
      "better": 3,
      "worse": 6,
      "tie": 0
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 166.48237834720274,
      "low": -625.9403798112695,
      "high": 141.87634912602962
    },
    "per_stem_mean_delta": {
      "c103C5": 21.231162005315014,
      "r105C5": -22.229964856368028,
      "rc108C5": 13.435601114507257,
      "c104C10": -116.42131188978462,
      "r103C10": 614.3661536457946,
      "rc108C10": -883.8127559259455,
      "c106C15": -1014.632960251289,
      "r105C15": -332.5109666113359,
      "rc108C15": -457.71309531447304
    }
  },
  "css_vs_no_forecast_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -118.7188045058143,
      "std": 520.0796933330378,
      "median": -19.194156398501292
    },
    "tally_stems": {
      "better": 2,
      "worse": 5,
      "tie": 2
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 173.35989777767927,
      "low": -518.4867287811427,
      "high": 281.04911976951405
    },
    "per_stem_mean_delta": {
      "c103C5": -19.194156398501292,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": 923.850450246653,
      "r103C10": 160.83344375575226,
      "rc108C10": -258.12310172913106,
      "c106C15": -958.3744392201367,
      "r105C15": -408.7398306344786,
      "rc108C15": -508.72160657248634
    }
  },
  "css_vs_no_terminal_au": {
    "metric": "accepted_unfulfilled_count",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 0.0,
      "std": 1.2747548783981961,
      "median": 0.0
    },
    "tally_stems": {
      "better": 4,
      "worse": 2,
      "tie": 3
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 0.4249182927993987,
      "low": -0.9798615831954134,
      "high": 0.9798615831954134
    },
    "per_stem_mean_delta": {
      "c103C5": 0.0,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": -1.5,
      "r103C10": -2.5,
      "rc108C10": 1.0,
      "c106C15": 1.5,
      "r105C15": 1.0,
      "rc108C15": 0.5
    }
  },
  "css_vs_no_predictive_charge_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": -74.63342412289607,
      "std": 605.1983795479558,
      "median": 0.0
    },
    "tally_stems": {
      "better": 3,
      "worse": 4,
      "tie": 2
    },
    "ci95": {
      "level": 0.95,
      "method": "stem_clustered_paired_t",
      "df": 8,
      "se": 201.73279318265193,
      "low": -539.8292452020914,
      "high": 390.56239695629927
    },
    "per_stem_mean_delta": {
      "c103C5": 32.6547236338415,
      "r105C5": 0.0,
      "rc108C5": 0.0,
      "c104C10": 111.48906713927386,
      "r103C10": 1296.6788694905586,
      "rc108C10": -377.30665034222886,
      "c106C15": -882.0209963473733,
      "r105C15": -403.2867802221225,
      "rc108C15": -449.90905045801384
    }
  },
  "css_vs_no_warm_init_economic": {
    "metric": "economic_objective",
    "unit": "stem_mean_of_realization_deltas",
    "n_stems": 9,
    "delta": {
      "n": 9,
      "mean": 334.54674734877165,
      "std": 657.4134517658122,
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
      "se": 219.13781725527073,
      "low": -170.78505924188266,
      "high": 839.878553939426
    },
    "per_stem_mean_delta": {
      "c103C5": 2.7372803300150252,
      "r105C5": 0.0,
      "rc108C5": -25.7467314108414,
      "c104C10": 643.2890926863021,
      "r103C10": 1923.9149374680583,
      "rc108C10": -5.451894528541743,
      "c106C15": -11.474568099339365,
      "r105C15": 582.2466812883965,
      "rc108C15": -98.59407159510471
    }
  }
}
```
