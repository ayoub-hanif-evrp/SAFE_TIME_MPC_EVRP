# Decision-advantage validation

**Gate pass:** `False`

```json
{
  "completed_delta": {
    "n": 18,
    "mean": -1.6666666666666667,
    "std": 3.646109933485114
  },
  "tally": {
    "better": 0,
    "worse": 5,
    "tie": 13
  }
}
```

BAP vs GN (dev): `{'completed_delta': {'n': 18, 'mean': -1.0555555555555556, 'std': 2.7540819378263675}, 'tally': {'better': 1, 'worse': 5, 'tie': 12}}`

Controller: `DecisionFocusedBAP` (feature screen + paired causal + confirmation batch).
