# BAP divergence audit — `c208C15` (inspected)

**Environment seed:** `1410663356`  
**Policy seed:** `595457899`  

> Inspected final-test cell. Correctness diagnosis only — **no parameter tuning**.

## Root cause (pre-fix)

BAP nested incumbent used time_limit*0.45 and a separate CertificateStore; cooperative wall-clock ALNS cutoffs amplify trajectory variance. Stage-1A matches incumbent budget, shares the store, and adds allow_override=False / equivalence_mode (iteration-primary) for deterministic checks.

## Closed-loop (iteration-primary equivalence)

```json
{
  "cce_greedy_nominal_iter": {
    "controller": "cce_greedy_nominal_iter",
    "completed": 15,
    "au": 0,
    "rejected": 0,
    "termination_reason": "cutoff_next_event_after_tmax",
    "fallback_count": 1
  },
  "bap_zero_override_iter": {
    "controller": "bap_zero_override_iter",
    "completed": 15,
    "au": 0,
    "rejected": 0,
    "termination_reason": "cutoff_next_event_after_tmax",
    "fallback_count": 1
  }
}
```

## Closed-loop (cooperative 0.35s wall clock)

```json
{
  "cce_greedy_nominal_0_35s": {
    "controller": "cce_greedy_nominal_0_35s",
    "completed": 15,
    "au": 0,
    "rejected": 0,
    "termination_reason": "cutoff_next_event_after_tmax",
    "fallback_count": 5
  },
  "bap_allow_override_0_35s": {
    "controller": "bap_allow_override_0_35s",
    "completed": 13,
    "au": 0,
    "rejected": 2,
    "termination_reason": "cutoff_next_event_after_tmax",
    "fallback_count": 0
  }
}
```

## Zero-override vs greedy-nominal first-action walk

- Epochs compared: 40
- All matched: **True**
- First divergence: `None`

Iteration-primary zero-override must match GN completed/AU. Wall-clock 0.35s runs remain cooperative (not hard-real-time) and may differ.
