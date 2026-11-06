# Triggering theory

## What slack does not prove

If a backup is already certified for every disturbance in the rectangle, extra time or battery slack does not create a new safety obligation to re-solve. Postponing an optional improvement cannot by itself make that certificate false. A trigger justified only by "slack is small, therefore re-optimize for safety" would be a manufactured theorem. The slack policy below is a heuristic.

## What can invalidate the certificate

Under Propositions 1–3, the committed certificate ceases to apply when any hypothesis changes:

- the rectangle is replaced,
- the measured battery is worse than every state in the predicted tube,
- a station or a road assumption in A7 fails,
- the action identity changes in a way the shift proposition does not cover,
- a new customer is accepted, which means the sequence changes.

A new announcement does not invalidate the backup. It does require an immediate accept-or-reject decision. Ignoring it until a timer expires can miss a window that was still feasible at the release instant. The policies below all treat `request_release` as immediate, except a negative control used only in a test (`ignore_requests=True`), which is not a proposed controller.

An arrival, a service completion, or a charge completion does not by itself require a new optimization when the stored suffix, realigned to the anchor, still passes Proposition 1.

## Policies

| Code | Policy | When a new solve is started | Label |
| --- | --- | --- | --- |
| B2 | `fixed_period` | Release, initial decision, and the replan timer | Schedule. Not a safety proof. |
| B3 | `every_event` | Every simulator trigger | Schedule. Not a safety proof. |
| B4 | `every_event` with the same anytime insertion and certified backup | Same as B3 | Anytime incumbent. The trigger is not new. |
| — | `slack_heuristic` | Release, plus a solve when the stored time margin is below 5 or the energy margin is below 1, unless the caller sets other thresholds | Heuristic. |
| B5 | `validity_aware` | Release, initial decision, and a hypothesis change (`bound_update`, `soc_discrepancy`, `disruption`) | This is Proposition 3 plus the list above. It is not a new self-triggered stability theorem. |

B4 and B3 share a trigger. They differ only in that every robust policy already keeps a certified incumbent. There is no second optimizer.

## Sufficient condition that is actually used

**Proposition 5.** Assume A1–A7, a committed certificate for \(\pi\), no new acceptance, an unchanged rectangle, and a realized anchor that still satisfies Proposition 2. Then \(\pi\), realigned to that anchor, remains certified without another solve.

**Proof.** Proposition 2 covers one realized arc inside the rectangle. Repeating it along the committed sequence covers a chain of such arcs. Proposition 3 covers a rejection. Nothing in either proof requires a new optimization. \(\square\)

The practical consequence is negative and useful: on events that are not in the list above, B5 does not start the worker. The backup is realigned and re-checked against the current anchor before it is dispatched, because a software cursor can fall behind the vehicle even when the mathematics still holds. That re-check is a certificate call, not an optimization.

If the realigned backup fails, the controller stops and reports infeasibility. It does not invent a depot return that the certificate rejected.

## What was measured

On one development run of the easy toy (factors \([1, 1.05]\), deadline 5 s, releases at 0, 5, and 10), the validity-aware policy started 4 optimizations and the every-event policy started 15. Both served C1, C2, and C3, with no commitment failure. Fixed period served the same three customers in 6 optimizations. One candidate was discarded as stale, and the unanswered announcement was tried on the next event. These are counts from a single run. Skipping solves did not raise service. It only avoided solves. A flag that also ignores releases is a counterexample to "skipping solves is always safe," not a controller.

A second construction, the `ignore_requests` flag, skips the release as well. That flag is not proved safe and is not a policy. It exists so the test can show that "do not solve yet" is the wrong response to a new request.

## Not claimed

There is no proof that B5 has a better service–computation trade-off than a well chosen fixed period. There is no Lyapunov function and no self-triggered MPC theorem in the sense of Brunner, Heemels, and Allgöwer or Gräfe and Trimpe. Those results remain the relevant theory for smooth plants.
