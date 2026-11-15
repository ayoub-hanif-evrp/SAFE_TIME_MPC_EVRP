# Forecast scoring causal audit

**Protocol:** `2026-11-14.v2`  
**Stems:** c101C5, c104C10, c106C15, r104C5, r103C10, r105C15, rc105C5, rc108C10, rc108C15  
**Rows:** 18  
**Wall seconds:** 1460.5397278000019  

## Supported conclusion

**negligible_decision_value**  
Under identical causal objective, paired mean completed delta (calibrated - empty-future) ~ -0.556 with tally better=7/worse=7/n=18. The large greedy_nominal gap is an unequal-objective artifact, not forecast value.

## Calibration (train-only, honest sample sizes)

```json
{
  "protocol_version": "2026-11-14.v2",
  "dynamicity": "medium",
  "train_stems": [
    "c101C5",
    "c101C10",
    "c103C15",
    "r104C5",
    "r102C10",
    "r102C15",
    "rc105C5",
    "rc102C10",
    "rc103C15"
  ],
  "n_train_stems": 9,
  "n_realizations_per_stem": 3,
  "n_episode_level_mean_estimates": 27,
  "n_raw_interarrival_gaps": 171,
  "calibrated_announcement_mean": 6.11763975749961,
  "mean_of_episode_means": 7.235932687000066,
  "mean_gap_by_customer_count": {
    "5": 9.646747632750657,
    "10": 8.328897947063698,
    "15": 3.732152481185844
  },
  "honesty_note": "n_episode_level_mean_estimates counts one mean per (stem, realization). n_raw_interarrival_gaps counts individual successive dynamic-release gaps. These are not interchangeable sample sizes."
}
```

## Mean completed services (repaired causal objective)

```json
{
  "b1": {
    "n": 18,
    "mean": 3.9444444444444446,
    "std": 3.9626524423780807
  },
  "m1": {
    "n": 18,
    "mean": 4.888888888888889,
    "std": 3.512815008087638
  },
  "cce_greedy_nominal": {
    "n": 18,
    "mean": 6.666666666666667,
    "std": 3.6622076273584425
  },
  "cce_causal_empty_future": {
    "n": 18,
    "mean": 4.444444444444445,
    "std": 3.091206165165235
  },
  "cce_old_fixed_catalogue": {
    "n": 18,
    "mean": 4.388888888888889,
    "std": 2.592724864350674
  },
  "cce_conditional_calibrated": {
    "n": 18,
    "mean": 3.888888888888889,
    "std": 2.7629670515778098
  },
  "stochastic_conditional_calibrated": {
    "n": 18,
    "mean": 3.888888888888889,
    "std": 3.894020890135344
  }
}
```

## Paired calibrated vs causal empty-future

- Stats: `{'n': 18, 'mean': -0.5555555555555556, 'std': 2.974840029751916}`
- Tally: `{'better': 7, 'worse': 7, 'tie': 4}`
- Greedy-nominal vs causal empty: `{'n': 18, 'mean': 2.2222222222222223, 'std': 2.9216344248413937}`

## Failures

```json
{}
```

## Action-difference audits

Logged episode blocks with first-action disagreements: **18** (44 epochs).

Disagreements occur on public state under matched seeds; see JSON `action_audits` for legs and forecast counts. No mechanism is claimed from score gaps alone.

## Perfect-information labeling

The former `perfect_info_diagnostic` is renamed to `release_statistics_diagnostic`.
A restricted offline hindsight comparator is recorded under `hindsight_offline` and does not feed online control.

## Reading

- `cce_greedy_nominal` is the old unequal objective (for diagnosis).
- `cce_causal_empty_future` is the fair no-forecast ablation (same causal scorer).
- `cce_conditional_calibrated` uses decision-epoch-conditioned forecasts with train-calibrated mu.
- Prior Schneider-v1 / stall-diagnostic artifacts remain frozen and are not re-used as fresh validation.
