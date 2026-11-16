# MPC decision-quality diagnosis

Offline hindsight is diagnostic only.

## Mechanism tallies (t=0 matched candidate sets)

```json
{
  "prediction_error": 2,
  "ranking_error": 2,
  "action_space_error": 2,
  "horizon_error": 0,
  "computation_error": 0,
  "feasibility_error": 0
}
```

## Per-stem closed-loop vs first divergence

| Stem | Δ econ CSS−GN | First divergence | Empty vs FC disagree | FC vs hindsight disagree | Hindsight gap vs empty | Mechanisms |
|---|---:|---|---|---|---:|---|
| r103C10 | -1387.5 | t=0.00 | False | False | 0.0 | — |
| rc108C10 | -932.8 | t=0.00 | False | False | 0.0 | — |
| rc108C15 | -1033.0 | t=0.00 | False | True | 1236.2 | A_or_B_prediction_or_ranking,B_or_C_ranking_or_action_space |
| c106C15 | 1780.9 | t=0.00 | False | True | 13.7 | A_or_B_prediction_or_ranking,B_or_C_ranking_or_action_space |

## Reading

- Large hindsight gap with empty≈forecast winners ⇒ **C action-space** or missing charge/route.
- Forecast≠hindsight while empty=hindsight ⇒ **B ranking** (forecast harms).
- Forecast=hindsight≠empty ⇒ prediction useful if used.
- Stage-0 / replay fails on promising actions ⇒ **F feasibility** mismatch.
- High candidate-gen time ⇒ **E computation**.

```json
[
  {
    "stem": "r103C10",
    "delta": -1387.4644792329823,
    "div": {
      "index": 0,
      "reason": "action_divergence",
      "css": {
        "time": 0.0,
        "trigger": "request_release",
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "S0",
            "charge"
          ]
        ],
        "newly": [],
        "rejected": [],
        "fallback": false,
        "status": "CERTIFIED_FEASIBLE",
        "optimize_seconds": 0.17136259999824688,
        "notes": [
          "commitment_safe_stochastic_mpc",
          "receding_horizon=1",
          "first_action_execution=1",
          "scoring_mode=causal_economic",
          "transactional_emit=1",
          "checkpointed_scoring=1",
          "commit_reserve_s=0.070",
          "use_forecast=1",
          "terminal_commitment=1",
          "quiescent",
          "approximation=restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse",
          "service_reward=100.0",
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=9",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "n_unique_first_actions=9",
          "n_empty_checkpoint=9",
          "n_scenario_expanded=3",
          "n_stochastic_terminal=3",
          "n_stochastic_failed=0",
          "n_nominal_backup_unchecked=6",
          "forecast_advantage_vs_empty_winner=0.0000",
          "selected_empty_future_due_to_forecast_margin",
          "selected=charge:v2->S0",
          "expected_value=74.315442",
          "feasibility_class=stochastic_terminal",
          "selection_mode=stochastic_terminal",
          "transactional_commit_ok"
        ]
      },
      "gn": {
        "time": 0.0,
        "trigger": "request_release",
        "legs": [
          [
            "v1",
            "C16",
            "service"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [
          "C16"
        ],
        "rejected": [],
        "fallback": false,
        "status": "CERTIFIED_FEASIBLE",
        "optimize_seconds": 0.0193602999788709,
        "notes": [
          "certificate_carrying_economic_mpc",
          "use_forecast=0",
          "persistent_certificate=1",
          "scoring_mode=greedy_nominal",
          "conditional_forecast=0",
          "quiescent",
          "hard_commitment_feasibility=1",
          "no_scenario_regret_floor=1",
          "n_valid_actions=9",
          "selected=alns",
          "expected_value=41.690481"
        ]
      }
    },
    "diag": {
      "time": 0.0,
      "accepted": [],
      "soc": [
        60.63,
        60.63
      ],
      "n_raw_candidates": 6,
      "n_feasible": 6,
      "stage0_fail": 0,
      "candidate_gen_seconds": 0.0006632999866269529,
      "empty_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 61.300123438040984,
        "hindsight_v": 528.7599647680224,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "forecast_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 61.300123438040984,
        "hindsight_v": 528.7599647680224,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "hindsight_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 61.300123438040984,
        "hindsight_v": 528.7599647680224,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "ranking_disagree_empty_forecast": false,
      "ranking_disagree_forecast_hindsight": false,
      "action_space_hindsight_gap_vs_empty": 0.0,
      "mechanisms": [],
      "top3_hindsight": [
        {
          "name": "alns",
          "legs": [
            [
              "v1",
              "D0",
              "return"
            ],
            [
              "v2",
              "D0",
              "return"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        },
        {
          "name": "charge:v1->S0",
          "legs": [
            [
              "v1",
              "S0",
              "charge"
            ],
            [
              "v2",
              "",
              "idle"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        },
        {
          "name": "charge:v2->S0",
          "legs": [
            [
              "v1",
              "",
              "idle"
            ],
            [
              "v2",
              "S0",
              "charge"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        }
      ],
      "top3_forecast": [
        {
          "name": "alns",
          "legs": [
            [
              "v1",
              "D0",
              "return"
            ],
            [
              "v2",
              "D0",
              "return"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        },
        {
          "name": "charge:v1->S0",
          "legs": [
            [
              "v1",
              "S0",
              "charge"
            ],
            [
              "v2",
              "",
              "idle"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        },
        {
          "name": "charge:v2->S0",
          "legs": [
            [
              "v1",
              "",
              "idle"
            ],
            [
              "v2",
              "S0",
              "charge"
            ]
          ],
          "newly": [],
          "empty_v": 0.0,
          "forecast_v": 61.300123438040984,
          "hindsight_v": 528.7599647680224,
          "empty_ok": true,
          "forecast_ok": true,
          "hindsight_ok": true
        }
      ]
    }
  },
  {
    "stem": "rc108C10",
    "delta": -932.7620201039069,
    "div": {
      "index": 0,
      "reason": "action_divergence",
      "css": {
        "time": 0.0,
        "trigger": "request_release",
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "S0",
            "charge"
          ]
        ],
        "newly": [],
        "rejected": [],
        "fallback": false,
        "status": "CERTIFIED_FEASIBLE",
        "optimize_seconds": 0.2807345000328496,
        "notes": [
          "commitment_safe_stochastic_mpc",
          "receding_horizon=1",
          "first_action_execution=1",
          "scoring_mode=causal_economic",
          "transactional_emit=1",
          "checkpointed_scoring=1",
          "commit_reserve_s=0.070",
          "use_forecast=1",
          "terminal_commitment=1",
          "quiescent",
          "approximation=restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse",
          "service_reward=100.0",
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=9",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "n_unique_first_actions=9",
          "n_empty_checkpoint=9",
          "cooperative_score_deadline_hit_checkpoint_b",
          "n_scenario_expanded=2",
          "n_stochastic_terminal=2",
          "n_stochastic_failed=0",
          "n_nominal_backup_unchecked=7",
          "forecast_advantage_vs_empty_winner=0.0000",
          "selected_empty_future_due_to_forecast_margin",
          "selected=charge:v2->S0",
          "expected_value=315.376742",
          "feasibility_class=stochastic_terminal",
          "selection_mode=stochastic_terminal",
          "transactional_commit_ok"
        ]
      },
      "gn": {
        "time": 0.0,
        "trigger": "request_release",
        "legs": [
          [
            "v1",
            "C80",
            "service"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [
          "C80"
        ],
        "rejected": [],
        "fallback": false,
        "status": "CERTIFIED_FEASIBLE",
        "optimize_seconds": 0.03957540000556037,
        "notes": [
          "certificate_carrying_economic_mpc",
          "use_forecast=0",
          "persistent_certificate=1",
          "scoring_mode=greedy_nominal",
          "conditional_forecast=0",
          "quiescent",
          "hard_commitment_feasibility=1",
          "no_scenario_regret_floor=1",
          "n_valid_actions=9",
          "selected=alns",
          "expected_value=84.768454"
        ]
      }
    },
    "diag": {
      "time": 0.0,
      "accepted": [],
      "soc": [
        77.75,
        77.75
      ],
      "n_raw_candidates": 6,
      "n_feasible": 6,
      "stage0_fail": 0,
      "candidate_gen_seconds": 0.0003569999826140702,
      "empty_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 203.20219742639543,
        "hindsight_v": 242.3856329505976,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "forecast_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 203.20219742639543,
        "hindsight_v": 242.3856329505976,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "hindsight_winner": {
        "name": "alns",
        "legs": [
          [
            "v1",
            "D0",
            "return"
          ],
          [
            "v2",
            "D0",
            "return"
          ]
        ],
        "newly": [],
        "empty_v": 0.0,
        "forecast_v": 203.20219742639543,
        "hindsight_v": 242.3856329505976,
        "empty_ok": true,
        "forecast_ok": true,
        "hindsight_ok": true
      },
      "ranking_disagree_empty_forecast": false,
      "ranking_disagree_forecast_hindsight": false,
      "action_space_hindsight_gap_vs_empty": 0.
```
