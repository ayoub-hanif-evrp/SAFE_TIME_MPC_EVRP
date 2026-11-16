# MPC forecast decision causality

## Offline ranking disagreements (same candidate set)

Disagreements: **2** / 4 diagnosed epochs.

```json
[
  {
    "time": 0.0,
    "n_feasible": 5,
    "empty_winner": {
      "name": "wait_idle",
      "value": 74.3875030502686,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "forecast_winner": {
      "name": "alns",
      "value": 109.570299109185,
      "legs": [
        [
          "v1",
          "C65",
          "service"
        ]
      ],
      "newly": [
        "C65"
      ]
    },
    "ranking_disagreement": true,
    "top3_empty": [
      {
        "name": "wait_idle",
        "value": 74.3875030502686,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v1->S0",
        "value": 74.3875030502686,
        "legs": [
          [
            "v1",
            "S0",
            "charge"
          ]
        ]
      },
      {
        "name": "alns",
        "value": 74.3875030502686,
        "legs": [
          [
            "v1",
            "C65",
            "service"
          ]
        ]
      }
    ],
    "top3_forecast": [
      {
        "name": "alns",
        "value": 109.570299109185,
        "legs": [
          [
            "v1",
            "C65",
            "service"
          ]
        ]
      },
      {
        "name": "wait_idle",
        "value": 54.28051498481107,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v1->S0",
        "value": 54.28051498481107,
        "legs": [
          [
            "v1",
            "S0",
            "charge"
          ]
        ]
      }
    ],
    "stem": "c103C5"
  },
  {
    "time": 0.0,
    "n_feasible": 9,
    "empty_winner": {
      "name": "wait_idle",
      "value": 35.22346103719342,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ],
        [
          "v2",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "forecast_winner": {
      "name": "reject:C34",
      "value": 157.82254731323064,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ],
        [
          "v2",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "ranking_disagreement": false,
    "top3_empty": [
      {
        "name": "wait_idle",
        "value": 35.22346103719342,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v2->S0",
        "value": 35.22346103719342,
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
        ]
      },
      {
        "name": "charge:v1->S0",
        "value": 35.22346103719342,
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
        ]
      }
    ],
    "top3_forecast": [
      {
        "name": "reject:C34",
        "value": 157.82254731323064,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "wait_idle",
        "value": 103.39832729362021,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v2->S0",
        "value": 103.39832729362021,
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
        ]
      }
    ],
    "stem": "c104C10"
  },
  {
    "time": 0.0,
    "n_feasible": 12,
    "empty_winner": {
      "name": "wait_idle",
      "value": 62.63691661546119,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ],
        [
          "v2",
          "",
          "idle"
        ],
        [
          "v3",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "forecast_winner": {
      "name": "alns",
      "value": 344.4489690637277,
      "legs": [
        [
          "v1",
          "C1",
          "service"
        ],
        [
          "v2",
          "D0",
          "return"
        ],
        [
          "v3",
          "D0",
          "return"
        ]
      ],
      "newly": [
        "C1"
      ]
    },
    "ranking_disagreement": true,
    "top3_empty": [
      {
        "name": "wait_idle",
        "value": 62.63691661546119,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ],
          [
            "v3",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v3->S0",
        "value": 62.63691661546119,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ],
          [
            "v3",
            "S0",
            "charge"
          ]
        ]
      },
      {
        "name": "charge:v2->S0",
        "value": 62.63691661546119,
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
          ],
          [
            "v3",
            "",
            "idle"
          ]
        ]
      }
    ],
    "top3_forecast": [
      {
        "name": "alns",
        "value": 344.4489690637277,
        "legs": [
          [
            "v1",
            "C1",
            "service"
          ],
          [
            "v2",
            "D0",
            "return"
          ],
          [
            "v3",
            "D0",
            "return"
          ]
        ]
      },
      {
        "name": "accept:C1@v1",
        "value": 344.4489690637277,
        "legs": [
          [
            "v1",
            "C1",
            "service"
          ],
          [
            "v2",
            "",
            "idle"
          ],
          [
            "v3",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "accept:C1@v3",
        "value": 333.65396987370417,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ],
          [
            "v2",
            "",
            "idle"
          ],
          [
            "v3",
            "C1",
            "service"
          ]
        ]
      }
    ],
    "stem": "c106C15"
  },
  {
    "time": 0.0,
    "n_feasible": 5,
    "empty_winner": {
      "name": "wait_idle",
      "value": 24.56960861770625,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "forecast_winner": {
      "name": "reject:C78",
      "value": 52.84899437408126,
      "legs": [
        [
          "v1",
          "",
          "idle"
        ]
      ],
      "newly": []
    },
    "ranking_disagreement": false,
    "top3_empty": [
      {
        "name": "wait_idle",
        "value": 24.56960861770625,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v1->S0",
        "value": 24.56960861770625,
        "legs": [
          [
            "v1",
            "S0",
            "charge"
          ]
        ]
      },
      {
        "name": "alns",
        "value": 24.56960861770625,
        "legs": [
          [
            "v1",
            "S1",
            "charge"
          ]
        ]
      }
    ],
    "top3_forecast": [
      {
        "name": "reject:C78",
        "value": 52.84899437408126,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "wait_idle",
        "value": 24.56960861770625,
        "legs": [
          [
            "v1",
            "",
            "idle"
          ]
        ]
      },
      {
        "name": "charge:v1->S0",
        "value": 24.56960861770625,
        "legs": [
          [
            "v1",
            "S0",
            "charge"
          ]
        ]
      }
    ],
    "stem": "r105C5"
  }
]
```

## Closed-loop empty-future vs finite-demand

```json
[
  {
    "stem": "c103C5",
    "outcomes": {
      "empty_future": {
        "completed": 4,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      },
      "finite_demand": {
        "completed": 4,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      }
    }
  },
  {
    "stem": "c104C10",
    "outcomes": {
      "empty_future": {
        "completed": 8,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      },
      "finite_demand": {
        "completed": 8,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      }
    }
  },
  {
    "stem": "c106C15",
    "outcomes": {
      "empty_future": {
        "completed": 11,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      },
      "finite_demand": {
        "completed": 10,
        "au": 0,
        "status": "UNKNOWN"
      }
    }
  },
  {
    "stem": "r105C5",
    "outcomes": {
      "empty_future": {
        "completed": 2,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      },
      "finite_demand": {
        "completed": 3,
        "au": 0,
        "status": "CERTIFIED_FEASIBLE"
      }
    }
  }
]
```

## Mechanism

When rankings disagree, finite-demand scenarios inflate expected value of early
accept/ALNS first actions relative to empty-future wait/idle under the same
candidate set and B1 recourse. With `n_scenarios=2`, Monte Carlo variance amplifies
flips. Closed-loop: on `c106C15` empty-future completed 11 (CERTIFIED_FEASIBLE)
while finite-demand completed 10 (UNKNOWN) — forecast harm is decision-ranking,
not missing candidates.

Restricted hindsight / offline ranking is diagnostic only — never used online.

## Focused solver response (Phase 3)

`forecast_override_margin` (corrected development uses 50.0): if the forecast-ranked
winner differs from the empty-future winner, keep the empty-future action unless the
forecast mean advantage exceeds the margin. Preserves the economic objective and hard
commitment constraints; does not add waiting/charging bonuses.
