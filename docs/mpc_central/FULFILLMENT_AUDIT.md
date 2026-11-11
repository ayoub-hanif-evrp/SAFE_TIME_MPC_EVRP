# Frontier `accepted_unfulfilled` audit

Source: `docs/commitment_safe_mpc/budget_frontier.json`.  
Module: `mpc_central/fulfillment_audit.py`.

## Method (Phase 3C repair)

`run_episode` now records:

- `termination_reason` ∈ `{natural_completion, cutoff_next_event_after_tmax, no_pending_events, ...}`
- `pending_next_event_time`
- `t_max`

**Cutoff is `termination_reason == cutoff_next_event_after_tmax`**, not `end_time >= t_max` (the clock may stop before `t_max` when the next event is beyond the horizon).

`no_feasible_continuation_count > 0` is recorded as a **flag**, not as proof that NFC caused AU.

## Labels

| Label | Meaning |
|-------|---------|
| `cutoff_censor_with_accepted_unfulfilled` | Cut off because next event > t_max, AU present |
| `natural_end_with_accepted_unfulfilled` | Natural completion with residual AU |
| `no_events_with_accepted_unfulfilled` | No pending events, AU present |
| `no_accepted_unfulfilled` | AU did not reproduce on re-run |
| `residual_accepts_term_*` | Other termination with AU |

## Results (31 re-runs, new schema)

| Label | Count |
|-------|------:|
| `cutoff_censor_with_accepted_unfulfilled` | 22 |
| `no_accepted_unfulfilled` | 9 |

Under the corrected terminator, most reproduced AU episodes are **time cutoffs** (`next_event > t_max`), not proven NFC causation. 9/31 did not reproduce AU (wall-clock search noise).
