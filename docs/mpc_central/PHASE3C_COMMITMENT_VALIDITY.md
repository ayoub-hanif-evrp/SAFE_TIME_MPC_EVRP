# Phase 3C — Commitment validity

## Reload feasibility (audit finding)

On capacity-3 geometry with demands 2+2, the route

`Must → D(reload) → Now`

is **nominally feasible** under `evaluate_route` (served `{Must,Now}`, end time 64). Phase 3B’s claim that `accept_now` is impossible because a direct `Must→Now` exceeds payload was therefore incomplete: infeasibility of one constructed route ≠ infeasibility of acceptance.

Regression: `test_case_c_reload_route_is_nominally_feasible`.

## Rebuilt Case C

Candidates (distinct):

| Action | Meaning |
|--------|---------|
| `accept_now_after_must` | Accept Now with validated single-tour `Must→Now` (capacity 4) |
| `reject_now_serve_must` | Reject Now; serve Must |

Plant expected values (causal reactive recourse):

| Action | E[value] | Notes |
|--------|----------|-------|
| `accept_now_after_must` | 200 | Must+Now; Futures miss tight windows |
| `reject_now_serve_must` | 250 | Must; Futures complete under high-p scenario |

Prior `Must` is seeded by a **logged accept decision**, not silent request-map mutation.

## Safety gate

Before dispatch, `evaluate_action_scenario` requires:

1. No route target in `RequestStatus.HIDDEN`.  
2. `validate_continuation(..., require_new=newly_accepted).ok` whenever priors or new accepts exist.  
3. Failed validation / dispatch → score `-1e9` with **actual** `validate_log` on the current log (`replay_ok` not hard-coded True).

## Commitment-specific MPC mechanism?

Case C now shows a **commitment-constrained service tradeoff** (accept Now vs keep futures) with validated continuations. It does **not** by itself establish a computation-aware MPC algorithm advantage (see fairness REVISE).
