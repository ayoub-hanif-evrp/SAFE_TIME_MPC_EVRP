# Corrected MPC development results

**Gate:** `FAIL` — No reliable clustered economic gain vs GN (delta=145.16217966006948, ci={'level': 0.95, 'method': 'stem_clustered_paired_t', 'df': 8, 'se': 184.05970488603126, 'low': -279.27949980711855, 'high': 569.6038591272576}, tally={'better': 7, 'worse': 2, 'tie': 0}).

Primary metric: `economic_objective`

Stems (all development): ['c103C5', 'r105C5', 'rc108C5', 'c104C10', 'r103C10', 'rc108C10', 'c106C15', 'r105C15', 'rc108C15']

## Summary

```json
{
  "b1": {
    "economic_objective": {
      "n": 18,
      "mean": -634.515155769826,
      "std": 1112.5784968930448,
      "median": -152.9657457883178
    },
    "completed_count": {
      "n": 18,
      "mean": 3.388888888888889,
      "std": 2.9731917666113885,
      "median": 2.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 3.2777777777777777,
      "std": 3.9527437314523626,
      "median": 2.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 3.0,
      "std": 2.42535625036333,
      "median": 2.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 153.9596002142705,
      "std": 83.92129953632343,
      "median": 130.91333239840077
    },
    "charge_time": {
      "n": 18,
      "mean": 160.72540399795932,
      "std": 215.61284443762312,
      "median": 42.295027943840154
    },
    "decision_latency": {
      "n": 929,
      "mean": 0.061280928632162765,
      "median": 0.0030018999823369086,
      "p50": 0.0030018999823369086,
      "p90": 0.2671822999836877,
      "p95": 0.3710447999765165,
      "p99": 0.4085260999854654,
      "max": 0.5533020999864675,
      "frac_over_budget": 0.0721205597416577
    },
    "deadline_overruns_sum": 67,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "m1": {
    "economic_objective": {
      "n": 18,
      "mean": -113.74040834490164,
      "std": 729.2034866101486,
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
      "mean": 197.07374167823497,
      "std": 105.00571568779918,
      "median": 180.52718481341452
    },
    "charge_time": {
      "n": 18,
      "mean": 220.8045442609651,
      "std": 313.4533401966911,
      "median": 62.654967089920675
    },
    "decision_latency": {
      "n": 958,
      "mean": 0.061072340814760324,
      "median": 0.00219870000728406,
      "p50": 0.002188800019212067,
      "p90": 0.23719519999576733,
      "p95": 0.35670220002066344,
      "p99": 0.3934685999993235,
      "max": 0.584496500028763,
      "frac_over_budget": 0.05741127348643006
    },
    "deadline_overruns_sum": 55,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "cce_greedy_nominal": {
    "economic_objective": {
      "n": 18,
      "mean": -172.48072842152817,
      "std": 888.4276442990428,
      "median": 226.09106782368647
    },
    "completed_count": {
      "n": 18,
      "mean": 4.277777777777778,
      "std": 3.0832670899084333,
      "median": 3.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.6111111111111112,
      "std": 2.9929110143586435,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 1.9444444444444444,
      "std": 2.4608038433722332,
      "median": 1.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 197.48072842152817,
      "std": 113.66671990087639,
      "median": 141.84826270721157
    },
    "charge_time": {
      "n": 18,
      "mean": 144.79705029112267,
      "std": 235.2440037402878,
      "median": 70.27159034461499
    },
    "decision_latency": {
      "n": 1001,
      "mean": 0.06847369630221412,
      "median": 0.009022600017488003,
      "p50": 0.009022600017488003,
      "p90": 0.23770489997696131,
      "p95": 0.26604340004269034,
      "p99": 0.5626011000131257,
      "max": 1.3455788999563083,
      "frac_over_budget": 0.029970029970029972
    },
    "deadline_overruns_sum": 30,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "stochastic_cce_causal": {
    "economic_objective": {
      "n": 18,
      "mean": 214.71346658116124,
      "std": 360.5707363095195,
      "median": 260.6246189144797
    },
    "completed_count": {
      "n": 18,
      "mean": 5.277777777777778,
      "std": 2.5851511630749395,
      "median": 5.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.5,
      "std": 1.0981267472114393,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.222222222222222,
      "std": 2.8810854889730786,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 188.06431119661653,
      "std": 91.05727643394837,
      "median": 193.59551206135524
    },
    "charge_time": {
      "n": 18,
      "mean": 174.5312477646645,
      "std": 214.48185306772538,
      "median": 65.1479836635185
    },
    "decision_latency": {
      "n": 1017,
      "mean": 0.16713250599781623,
      "median": 0.06301440001698211,
      "p50": 0.06301440001698211,
      "p90": 0.4375197000335902,
      "p95": 0.5247864000266418,
      "p99": 0.8047086999868043,
      "max": 0.9389715000288561,
      "frac_over_budget": 0.23893805309734514
    },
    "deadline_overruns_sum": 243,
    "certificate_loss_events_sum": 0,
    "replay_failures": 0
  },
  "commitment_safe_stochastic_mpc": {
    "economic_objective": {
      "n": 18,
      "mean": -27.318548761458647,
      "std": 581.9258651427231,
      "median": 191.32074701384437
    },
    "completed_count": {
      "n": 18,
      "mean": 3.888888888888889,
      "std": 2.193275522213265,
      "median": 3.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.0,
      "std": 1.909727421264462,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 3.888888888888889,
      "std": 3.4108630767160055,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 166.20743765034754,
      "std": 68.810848400138,
      "median": 165.2900657730257
    },
    "charge_time": {
      "n": 18,
      "mean": 153.93815627540857,
      "std": 200.5097083535967,
      "median": 53.91784711109097
    },
    "decision_latency": {
      "n": 913,
      "mean": 0.1699252238762101,
      "median": 0.07651039998745546,
      "p50": 0.07651039998745546,
      "p90": 0.37309849995654076,
      "p95": 0.5088848000159487,
      "p99": 0.7284910000162199,
      "max": 1.010608599986881,
      "frac_over_budget": 0.11062431544359255
    },
    "deadline_overruns_sum": 101,
    "certificate_loss_events_sum": 154,
    "replay_failures": 0
  },
  "css_mpc_no_forecast": {
    "economic_objective": {
      "n": 18,
      "mean": 91.40025574435566,
      "std": 377.92938257914,
      "median": 226.5348641490504
    },
    "completed_count": {
      "n": 18,
      "mean": 4.388888888888889,
      "std": 1.6138696240399015,
      "median": 5.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.6111111111111112,
      "std": 1.4199788270537859,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 5.0,
      "std": 3.9556363361069242,
      "median": 3.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 194.71085536675548,
      "std": 86.71565126316726,
      "median": 191.01472629722753
    },
    "charge_time": {
      "n": 18,
      "mean": 212.99877113970075,
      "std": 286.7962096742875,
      "median": 52.33424798276362
    },
    "decision_latency": {
      "n": 943,
      "mean": 0.18220687052111556,
      "median": 0.09988940000766888,
      "p50": 0.09988940000766888,
      "p90": 0.40815570001723245,
      "p95": 0.5403462999965996,
      "p99": 1.0131537999841385,
      "max": 1.5911228000186384,
      "frac_over_budget": 0.11664899257688228
    },
    "deadline_overruns_sum": 110,
    "certificate_loss_events_sum": 95,
    "replay_failures": 0
  },
  "css_mpc_no_terminal": {
    "economic_objective": {
      "n": 18,
      "mean": -19.178260212648993,
      "std": 518.3009137455091,
      "median": 228.1280734305002
    },
    "completed_count": {
      "n": 18,
      "mean": 4.111111111111111,
      "std": 1.7111705277859945,
      "median": 4.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.0,
      "std": 1.7489492643904123,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.888888888888889,
      "std": 3.4108630767160055,
      "median": 3.5
    },
    "executed_distance": {
      "n": 18,
      "mean": 180.2893713237601,
      "std": 74.37046025139685,
      "median": 170.27486784289158
    },
    "charge_time": {
      "n": 18,
      "mean": 177.44783957471117,
      "std": 229.54743730865783,
      "median": 54.15575922197229
    },
    "decision_latency": {
      "n": 943,
      "mean": 0.17354430498456294,
      "median": 0.07677420001709834,
      "p50": 0.07677420001709834,
      "p90": 0.41017499996814877,
      "p95": 0.5552983999950811,
      "p99": 0.7033367999829352,
      "max": 0.8967985999770463,
      "frac_over_budget": 0.14952279957582185
    },
    "deadline_overruns_sum": 141,
    "certificate_loss_events_sum": 132,
    "replay_failures": 0
  },
  "css_mpc_no_predictive_charge": {
    "economic_objective": {
      "n": 18,
      "mean": 47.314875361437416,
      "std": 429.91574256407495,
      "median": 180.00618518030063
    },
    "completed_count": {
      "n": 18,
      "mean": 3.2222222222222223,
      "std": 1.2153699778283713,
      "median": 3.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.5,
      "std": 1.5434872662825796,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 6.277777777777778,
      "std": 3.937833915709551,
      "median": 6.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 149.9073468607848,
      "std": 75.89098597105173,
      "median": 123.51916104121781
    },
    "charge_time": {
      "n": 18,
      "mean": 110.44210453870676,
      "std": 195.98315034572926,
      "median": 24.913994808677966
    },
    "decision_latency": {
      "n": 888,
      "mean": 0.20306323873910104,
      "median": 0.20944600002258085,
      "p50": 0.20932389999506995,
      "p90": 0.4404565999866463,
      "p95": 0.5976603999733925,
      "p99": 0.9480447000241838,
      "max": 1.3600780999986455,
      "frac_over_budget": 0.13175675675675674
    },
    "deadline_overruns_sum": 117,
    "certificate_loss_events_sum": 90,
    "replay_failures": 0
  },
  "css_mpc_no_warm_init": {
    "economic_objective": {
      "n": 18,
      "mean": -361.8652961102303,
      "std": 610.515567008373,
      "median": -346.485130843317
    },
    "completed_count": {
      "n": 18,
      "mean": 2.3333333333333335,
      "std": 1.9402850002906638,
      "median": 2.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 1.9444444444444444,
      "std": 2.0714366206096226,
      "median": 2.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 1.8888888888888888,
      "std": 1.323493100445977,
      "median": 2.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 109.0875183324525,
      "std": 55.869435583026345,
      "median": 109.34325477547583
    },
    "charge_time": {
      "n": 18,
      "mean": 102.81951707036701,
      "std": 181.80445582886125,
      "median": 22.87868879517702
    },
    "decision_latency": {
      "n": 920,
      "mean": 0.15189797902200117,
      "median": 0.029093149991240352,
      "p50": 0.02865560003556311,
      "p90": 0.36469159997068346,
      "p95": 0.5012138999882154,
      "p99": 0.9007040000287816,
      "max": 2.345778800023254,
      "frac_over_budget": 0.10760869565217392
    },
    "deadline_overruns_sum": 99,
    "certificate_loss_events_sum": 432,
    "replay_failures": 0
  },
  "css_mpc_no_warm_no_backup": {
    "economic_objective": {
      "n": 18,
      "mean": -434.4159675269252,
      "std": 701.3347647053099,
      "median": -306.1200815285913
    },
    "completed_count": {
      "n": 18,
      "mean": 2.0555555555555554,
      "std": 1.8302112453523989,
      "median": 1.5
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 2.1666666666666665,
      "std": 2.455486054675506,
      "median": 1.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 2.9444444444444446,
      "std": 3.1895458319922425,
      "median": 2.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 98.3048564158141,
      "std": 47.15230875002644,
      "median": 93.59220740730746
    },
    "charge_time": {
      "n": 18,
      "mean": 73.10002962110813,
      "std": 144.32121004374258,
      "median": 0.0
    },
    "decision_latency": {
      "n": 858,
      "mean": 0.14130109918309486,
      "median": 0.015161599993007258,
      "p50": 0.01511359994765371,
      "p90": 0.32982929999707267,
      "p95": 0.5936702999752015,
      "p99": 1.0442242000135593,
      "max": 1.9333382999757305,
      "frac_over_budget": 0.09673659673659674
    },
    "deadline_overruns_sum": 83,
    "certificate_loss_events_sum": 611,
    "replay_failures": 0
  },
  "css_mpc_no_energy_gate": {
    "economic_objective": {
      "n": 18,
      "mean": 116.72708281856437,
      "std": 481.19987445683756,
      "median": 226.09106782368647
    },
    "completed_count": {
      "n": 18,
      "mean": 4.277777777777778,
      "std": 2.6525360906910014,
      "median": 4.0
    },
    "accepted_unfulfilled_count": {
      "n": 18,
      "mean": 0.4444444444444444,
      "std": 1.464168996281919,
      "median": 0.0
    },
    "rejected_count": {
      "n": 18,
      "mean": 4.666666666666667,
      "std": 3.9107694443752146,
      "median": 3.0
    },
    "executed_distance": {
      "n": 18,
      "mean": 199.9395838481023,
      "std": 97.41834860118078,
      "median": 165.2900657730257
    },
    "charge_time": {
      "n": 18,
      "mean": 207.48967061810487,
      "std": 291.8933553714037,
      "median": 49.65928424033712
    },
    "decision_latency": {
      "n": 953,
      "mean": 0.17290241532025277,
      "median": 0.061305099981836975,
      "p50": 0.061305099981836975,
      "p90": 0.39574959996389225,
      "p95": 0.5407746999990195,
      "p99": 0.8598715999978594,
      "max": 2.099786499980837,
      "frac_over_budget": 0.12172088142707241
    },
    "deadline_overruns_sum": 116,
    "certificate_loss_events_sum": 103,
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

Reproduce: `python -m safe_time_evrp.mpc_central.mpc_corrected_development_eval`
