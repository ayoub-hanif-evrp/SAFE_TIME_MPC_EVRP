# MPC certificate-loss audit

Replayed development cells that previously ended in `CERTIFIED_FEASIBILITY_LOST`.

## Summary

```json
[
  {
    "stem": "c106C15",
    "realization_index": 1,
    "environment_seed": 1999353437,
    "final_status": "UNKNOWN",
    "n_loss_events": 5,
    "first_loss": {
      "time": 523.7378501186831,
      "trigger": "arrive",
      "outstanding": [
        "C89"
      ],
      "had_fallback_routes": false,
      "notes": [
        "certificate_invalidated_on_recheck",
        "n_valid_actions=1",
        "adaptive_n_scenarios=2",
        "n_scenarios_scored=2",
        "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
        "fallback_path_no_new_accepts",
        "status=CERTIFIED_FEASIBILITY_LOST",
        "existing_obligations_uncovered_by_fallback"
      ]
    },
    "all_losses": [
      {
        "time": 523.7378501186831,
        "trigger": "arrive",
        "outstanding": [
          "C89"
        ],
        "had_fallback_routes": false,
        "notes": [
          "certificate_invalidated_on_recheck",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 554.6378501186831,
        "trigger": "replan_interval",
        "outstanding": [
          "C89"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 585.5378501186831,
        "trigger": "replan_interval",
        "outstanding": [
          "C89"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 616.4378501186831,
        "trigger": "replan_interval",
        "outstanding": [
          "C89"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 642.4580240038441,
        "trigger": "charge_end",
        "outstanding": [
          "C89"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:impossible_charge:impossible_charge: duration does not match the linear rate",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      }
    ],
    "completed": 4,
    "accepted_unfulfilled": 0,
    "interpretation": "Fallback could not revalidate existing obligations after certificate advance/invalidation or scored-set exhaustion; status CERTIFIED_FEASIBILITY_LOST is an assumption-failure signal, not RF preservation."
  },
  {
    "stem": "r103C10",
    "realization_index": 0,
    "environment_seed": 951066033,
    "final_status": "CERTIFIED_FEASIBILITY_LOST",
    "n_loss_events": 24,
    "first_loss": {
      "time": 3.7949000581864594,
      "trigger": "request_release",
      "outstanding": [
        "C16",
        "C81",
        "C91"
      ],
      "had_fallback_routes": false,
      "notes": [
        "n_valid_actions=2",
        "adaptive_n_scenarios=2",
        "n_scenarios_scored=2",
        "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
        "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
        "fallback_path_no_new_accepts",
        "status=CERTIFIED_FEASIBILITY_LOST",
        "existing_obligations_uncovered_by_fallback"
      ]
    },
    "all_losses": [
      {
        "time": 3.7949000581864594,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 4.3289030476736094,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 4.434092642096439,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:budget",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 9.736671936460471,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 10.895057352152689,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 12.319683184655762,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 13.228944183342884,
        "trigger": "request_release",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 18.978944183342882,
        "trigger": "replan_interval",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 24.728944183342882,
        "trigger": "replan_interval",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 27.586228448267445,
        "trigger": "arrive",
        "outstanding": [
          "C16",
          "C81",
          "C91"
        ],
        "had_fallback_routes": false,
        "notes": [
          "n_valid_actions=2",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "reject:commit_only:rollout:replay_failed:replay:travel_timing:travel_timing: D0->C16",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 157.69697215913124,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "certificate_invalidated_on_recheck",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C18",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 161.89088154306972,
        "trigger": "charge_end",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C18",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 167.64088154306972,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 167.75836045997312,
        "trigger": "arrive",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 173.50836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 179.25836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 185.00836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 190.75836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 196.50836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 202.25836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 208.00836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 213.75836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 219.50836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 225.25836045997312,
        "trigger": "replan_interval",
        "outstanding": [
          "C18",
          "C27",
          "C53",
          "C83"
        ],
        "had_fallback_routes": false,
        "notes": [
          "au_penalty=250.0",
          "distance_penalty=1.0",
          "n_valid_actions=0",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      }
    ],
    "completed": 4,
    "accepted_unfulfilled": 4,
    "interpretation": "Fallback could not revalidate existing obligations after certificate advance/invalidation or scored-set exhaustion; status CERTIFIED_FEASIBILITY_LOST is an assumption-failure signal, not RF preservation."
  },
  {
    "stem": "r105C15",
    "realization_index": 0,
    "environment_seed": 1720731349,
    "final_status": "CERTIFIED_FEASIBLE",
    "n_loss_events": 4,
    "first_loss": {
      "time": 140.0,
      "trigger": "service_end",
      "outstanding": [
        "C28",
        "C5",
        "C57",
        "C69"
      ],
      "had_fallback_routes": false,
      "notes": [
        "certificate_invalidated_on_recheck",
        "n_valid_actions=1",
        "adaptive_n_scenarios=2",
        "n_scenarios_scored=2",
        "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C57",
        "fallback_path_no_new_accepts",
        "status=CERTIFIED_FEASIBILITY_LOST",
        "existing_obligations_uncovered_by_fallback"
      ]
    },
    "all_losses": [
      {
        "time": 140.0,
        "trigger": "service_end",
        "outstanding": [
          "C28",
          "C5",
          "C57",
          "C69"
        ],
        "had_fallback_routes": false,
        "notes": [
          "certificate_invalidated_on_recheck",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C57",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 145.75,
        "trigger": "replan_interval",
        "outstanding": [
          "C28",
          "C5",
          "C57",
          "C69"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C57",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 151.5,
        "trigger": "replan_interval",
        "outstanding": [
          "C28",
          "C5",
          "C57",
          "C69"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C57",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      },
      {
        "time": 157.25,
        "trigger": "replan_interval",
        "outstanding": [
          "C28",
          "C5",
          "C57",
          "C69"
        ],
        "had_fallback_routes": false,
        "notes": [
          "distance_penalty=1.0",
          "n_valid_actions=1",
          "adaptive_n_scenarios=2",
          "n_scenarios_scored=2",
          "reject:alns:rollout:replay_failed:replay:travel_timing:travel_timing: S0->C57",
          "fallback_path_no_new_accepts",
          "status=CERTIFIED_FEASIBILITY_LOST",
          "existing_obligations_uncovered_by_fallback"
        ]
      }
    ],
    "completed": 8,
    "accepted_unfulfilled": 0,
    "interpretation": "Fallback could not revalidate existing obligations after certificate advance/invalidation or scored-set exhaustion; status CERTIFIED_FEASIBILITY_LOST is an assumption-failure signal, not RF preservation."
  }
]
```

## Scientific reading

| Episode | First loss | Outstanding | Dominant reject | Classification |
|---|---|---|---|---|
| `c106C15` r1 | t≈523.7 arrive | C89 | `impossible_charge` duration≠linear rate | Plant/replay mismatch after charge; not RF preservation |
| `r103C10` r0 | t≈3.79 request_release | C16,C81,C91 | `travel_timing` D0→C16 | Real open-loop plan invalid under Validate; fallback empty |
| `r105C15` r0 | t≈140 service_end | C28,C5,C57,C69 | `travel_timing` S0→C57 | Certificate invalidated; re-solve fails; later recovered to CERTIFIED_FEASIBLE |

- Loss means **no independently validated backup** for outstanding accepted customers.
- Causes mix **real infeasibility of scored candidates**, **charge/travel replay mismatch**, and **budget exhaustion** — not a single bookkeeping bug.
- This falsifies unconditional recursive feasibility of the viable set.
- The controller correctly refuses `CERTIFIED_FEASIBLE` when uncovered (certified-emission soundness).
- See weakened theorem in `docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`.

## Minimal counterexample class

A certified plan that is later invalidated by plant advance, with ALNS/commit_only
candidates failing `validate_continuation` / replay and empty fallback routes, yields
`CERTIFIED_FEASIBILITY_LOST` with nonempty outstanding accepts. Deterministic seeds
above reproduce this class.
