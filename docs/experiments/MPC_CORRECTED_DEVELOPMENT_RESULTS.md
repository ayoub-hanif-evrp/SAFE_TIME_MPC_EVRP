# Corrected MPC development results

**Gate:** `FAIL` — No reliable clustered economic gain vs GN (delta=72.6196464589811, ci={'level': 0.95, 'method': 'stem_clustered_paired_t', 'df': 8, 'se': 259.769103033488, 'low': -526.4079051362423, 'high': 671.6471980542044}, tally={'better': 4, 'worse': 5, 'tie': 0}).

Primary metric: `economic_objective`

Stems (all development): ['c103C5', 'r105C5', 'rc108C5', 'c104C10', 'r103C10', 'rc108C10', 'c106C15', 'r105C15', 'rc108C15']

## Summary

```json
{
  "b1": {
    "economic_objective": {
      "n": 18,
      "mean": -726.8278984319102,
      "std": 1146.6652379847576,
      "median": -355.44887611244036
    },
    "completed_count": {
      "n": 18,
      "mean": 3.0555555555555554,
      "std": 2.577555207880755,
      "median": 2.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 3.5555555555555554,
      "std": 4.133396583956279,
      "median": 2.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 2.888888888888889,
      "std": 2.517909704704629,
      "median": 2.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 143.49456509857683,
      "std": 77.55031085713055,
      "median": 113.83660490518469
    },
    "charge_time": {
      "n": 18,
      "mean": 120.47006623183987,
      "std": 168.75409590897334,
      "median": 22.97603196518678
    },
    "decision_latency": {
      "n": 915,
      "mean": 0.04647655825103923,
      "median": 0.0019178999937139452,
      "p50": 0.0019178999937139452,
      "p90": 0.1982842999859713,
      "p95": 0.3506913000019267,
      "p99": 0.38498259999323636,
      "max": 0.4170989000122063,
      "frac_over_budget": 0.05136612021857923
    },
    "deadline_overruns_sum": 47,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "m1": {
    "economic_objective": {
      "n": 18,
      "mean": -113.77156592972466,
      "std": 729.18449469557,
      "median": 157.27228491174498
    },
    "completed_count": {
      "n": 18,
      "mean": 4.722222222222222,
      "std": 3.2322921307178683,
      "median": 4.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.5555555555555556,
      "std": 2.52568504911445,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 3.7222222222222223,
      "std": 2.492472326958435,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 197.10489926305797,
      "std": 105.03615001768772,
      "median": 180.52718481341452
    },
    "charge_time": {
      "n": 18,
      "mean": 220.8045442609651,
      "std": 313.4533401966911,
      "median": 62.654967089920675
    },
    "decision_latency": {
      "n": 963,
      "mean": 0.04871300726801134,
      "median": 0.001469499955419451,
      "p50": 0.001469499955419451,
      "p90": 0.18595150002511218,
      "p95": 0.27982640004483983,
      "p99": 0.39699199999449775,
      "max": 0.47651850001420826,
      "frac_over_budget": 0.030114226375908618
    },
    "deadline_overruns_sum": 29,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "cce_greedy_nominal": {
    "economic_objective": {
      "n": 18,
      "mean": 41.9719102421806,
      "std": 766.1245701165877,
      "median": 294.9810976244278
    },
    "completed_count": {
      "n": 18,
      "mean": 5.111111111111111,
      "std": 3.305768378934525,
      "median": 6.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.0,
      "std": 2.4733877696033693,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 2.611111111111111,
      "std": 2.746953154676455,
      "median": 2.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 219.13920086893052,
      "std": 120.58892823010146,
      "median": 189.15515397886014
    },
    "charge_time": {
      "n": 18,
      "mean": 155.75882076860245,
      "std": 230.6995246918306,
      "median": 86.44406632220542
    },
    "decision_latency": {
      "n": 1032,
      "mean": 0.053388496995438794,
      "median": 0.006344349996652454,
      "p50": 0.006333999976050109,
      "p90": 0.21977299998980016,
      "p95": 0.2470958000048995,
      "p99": 0.3243602000293322,
      "max": 0.9567276999587193,
      "frac_over_budget": 0.009689922480620155
    },
    "deadline_overruns_sum": 10,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "stochastic_cce_causal": {
    "economic_objective": {
      "n": 18,
      "mean": -194.19894966943792,
      "std": 1024.0353382194608,
      "median": 209.0693024543534
    },
    "completed_count": {
      "n": 18,
      "mean": 4.388888888888889,
      "std": 2.404380533866049,
      "median": 4.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.8333333333333333,
      "std": 3.6177666168670477,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 3.7777777777777777,
      "std": 2.712835624246889,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 174.7545052249935,
      "std": 82.87157390319624,
      "median": 171.51628833758122
    },
    "charge_time": {
      "n": 18,
      "mean": 178.41387838354362,
      "std": 272.1283205848895,
      "median": 52.62083692976241
    },
    "decision_latency": {
      "n": 1007,
      "mean": 0.13512638232273272,
      "median": 0.04332170000998303,
      "p50": 0.04332170000998303,
      "p90": 0.396147099963855,
      "p95": 0.45135089999530464,
      "p99": 0.5512178000062704,
      "max": 0.6649555999902077,
      "frac_over_budget": 0.1906653426017875
    },
    "deadline_overruns_sum": 192,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "commitment_safe_stochastic_mpc": {
    "economic_objective": {
      "n": 18,
      "mean": 114.59155670116166,
      "std": 439.8797793531265,
      "median": 203.95971569728218
    },
    "completed_count": {
      "n": 18,
      "mean": 4.722222222222222,
      "std": 2.7824144309141796,
      "median": 3.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.7222222222222222,
      "std": 1.4473324572571655,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.277777777777778,
      "std": 3.3042851955596646,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 177.07510996550502,
      "std": 107.27627646705672,
      "median": 127.80001769770891
    },
    "charge_time": {
      "n": 18,
      "mean": 186.40116880008654,
      "std": 284.7647291559382,
      "median": 58.060911322325154
    },
    "decision_latency": {
      "n": 999,
      "mean": 0.14665569409300844,
      "median": 0.0551528999931179,
      "p50": 0.0551528999931179,
      "p90": 0.35286980000091717,
      "p95": 0.38788599998224527,
      "p99": 0.5741249999846332,
      "max": 0.7187685000244528,
      "frac_over_budget": 0.23323323323323322
    },
    "deadline_overruns_sum": 233,
    "certificate_loss_events_sum": 147,
    "replay_failures": 0
  },
  "css_mpc_no_forecast": {
    "economic_objective": {
      "n": 18,
      "mean": 117.5011980985467,
      "std": 373.59141878967523,
      "median": 179.5170901503362
    },
    "completed_count": {
      "n": 18,
      "mean": 4.277777777777778,
      "std": 2.630266270474298,
      "median": 4.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.5,
      "std": 1.200490095997562,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.777777777777778,
      "std": 3.9638892896565103,
      "median": 3.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 185.27657967923108,
      "std": 89.22400085547088,
      "median": 162.2936098162528
    },
    "charge_time": {
      "n": 18,
      "mean": 186.82005920498943,
      "std": 245.29699248857696,
      "median": 59.61202359867611
    },
    "decision_latency": {
      "n": 990,
      "mean": 0.11731833030188672,
      "median": 0.03512344998307526,
      "p50": 0.03500630002235994,
      "p90": 0.35113730002194643,
      "p95": 0.35936870001023635,
      "p99": 0.488913000037428,
      "max": 0.576333099976182,
      "frac_over_budget": 0.16464646464646465
    },
    "deadline_overruns_sum": 163,
    "certificate_loss_events_sum": 112,
    "replay_failures": 0
  },
  "css_mpc_no_terminal": {
    "economic_objective": {
      "n": 18,
      "mean": -90.31396332743962,
      "std": 923.2205569685309,
      "median": 162.89638480125774
    },
    "completed_count": {
      "n": 18,
      "mean": 4.777777777777778,
      "std": 2.7771241060949357,
      "median": 4.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.5555555555555556,
      "std": 3.2398660506483585,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 3.388888888888889,
      "std": 2.5237434587833274,
      "median": 2.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 179.20285221632852,
      "std": 92.70561492065548,
      "median": 174.37436900817602
    },
    "charge_time": {
      "n": 18,
      "mean": 172.2822533153536,
      "std": 262.922358424167,
      "median": 63.025378973765825
    },
    "decision_latency": {
      "n": 1008,
      "mean": 0.1363699244037788,
      "median": 0.05241554998792708,
      "p50": 0.052277799986768514,
      "p90": 0.39178840001113713,
      "p95": 0.4290649999747984,
      "p99": 0.5343556000152603,
      "max": 0.7198551000328735,
      "frac_over_budget": 0.18452380952380953
    },
    "deadline_overruns_sum": 186,
    "certificate_loss_events_sum": 201,
    "replay_failures": 0
  },
  "css_mpc_no_predictive_charge": {
    "economic_objective": {
      "n": 18,
      "mean": -27.153181542696117,
      "std": 690.0035756965252,
      "median": 187.51630249169025
    },
    "completed_count": {
      "n": 18,
      "mean": 3.5555555555555554,
      "std": 2.3319323525205498,
      "median": 3.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.9444444444444444,
      "std": 2.338230155788328,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 5.388888888888889,
      "std": 3.632190861933929,
      "median": 4.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 146.59762598714053,
      "std": 71.68841990784664,
      "median": 113.68904401925377
    },
    "charge_time": {
      "n": 18,
      "mean": 91.35468585379793,
      "std": 159.78838924055984,
      "median": 26.10464350856994
    },
    "decision_latency": {
      "n": 889,
      "mean": 0.17305881721012115,
      "median": 0.08156550000421703,
      "p50": 0.08156550000421703,
      "p90": 0.36673959996551275,
      "p95": 0.4403842000174336,
      "p99": 0.7762719999882393,
      "max": 1.4324988999869674,
      "frac_over_budget": 0.281214848143982
    },
    "deadline_overruns_sum": 250,
    "certificate_loss_events_sum": 107,
    "replay_failures": 0
  },
  "css_mpc_no_warm_init": {
    "economic_objective": {
      "n": 18,
      "mean": -473.53678864862167,
      "std": 761.2513355955956,
      "median": -306.68959983804956
    },
    "completed_count": {
      "n": 18,
      "mean": 2.611111111111111,
      "std": 2.3044429948123843,
      "median": 2.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 2.5,
      "std": 2.6178122882419563,
      "median": 2.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.277777777777778,
      "std": 3.2864347848042326,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 109.64789975973278,
      "std": 44.89958772761029,
      "median": 98.07751199863668
    },
    "charge_time": {
      "n": 18,
      "mean": 96.32675927022487,
      "std": 141.96959298526116,
      "median": 29.51907534894611
    },
    "decision_latency": {
      "n": 944,
      "mean": 0.1450846793434767,
      "median": 0.04695464999531396,
      "p50": 0.046571899962145835,
      "p90": 0.35304329998325557,
      "p95": 0.4081849999492988,
      "p99": 0.7286056999582797,
      "max": 1.3870974999736063,
      "frac_over_budget": 0.21927966101694915
    },
    "deadline_overruns_sum": 207,
    "certificate_loss_events_sum": 404,
    "replay_failures": 0
  },
  "css_mpc_no_warm_no_backup": {
    "economic_objective": {
      "n": 18,
      "mean": -368.78386369305906,
      "std": 712.3071829395022,
      "median": 56.49643512641214
    },
    "completed_count": {
      "n": 18,
      "mean": 2.1666666666666665,
      "std": 1.5434872662825796,
      "median": 2.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.9444444444444444,
      "std": 2.5315008852509107,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.777777777777778,
      "std": 3.5736874275830783,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 99.33941924861462,
      "std": 44.683715187328154,
      "median": 93.87893836014766
    },
    "charge_time": {
      "n": 18,
      "mean": 118.83312399877279,
      "std": 184.20893961703442,
      "median": 32.403975348452015
    },
    "decision_latency": {
      "n": 926,
      "mean": 0.1409507377980102,
      "median": 0.05040850001387298,
      "p50": 0.0503317000111565,
      "p90": 0.35199520003516227,
      "p95": 0.38637399999424815,
      "p99": 0.7681146999821067,
      "max": 1.5557028999901377,
      "frac_over_budget": 0.18250539956803455
    },
    "deadline_overruns_sum": 169,
    "certificate_loss_events_sum": 512,
    "replay_failures": 0
  }
}
```

## Clustered paired effects

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

Reproduce: `python -m safe_time_evrp.mpc_central.mpc_corrected_development_eval`
