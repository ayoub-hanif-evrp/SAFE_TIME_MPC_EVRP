# Real-time semantics (Part 2.5)

## Decision interval

Let a decision begin at plant time \(t\) with observation version \(v\), and let the solver wall time be \(\delta\).

1. If the next scheduled plant event is at \(t'\) with \(t < t' \le t+\delta\):
   - the candidate computed from \(v\) is **stale**;
   - the staged backup is discarded;
   - plant time remains \(t\) (it does not jump to \(t+\delta\) and does not move backward);
   - **no** `apply_decision` is performed;
   - already dispatched noninterruptible actions stay on the event queue;
   - the episode loop then pops the intervening event at \(t'\) and may decide again.
2. If no event falls in \((t, t+\delta]\):
   - plant time becomes \(t+\delta\);
   - the candidate is revalidated against the new observation version;
   - only then may `commit` replace the backup and `apply_decision` run.

## Observation version

`observation_version` covers:

- vehicle status, node, locked destination, SOC, load, onboard set;
- accepted commitments and the full request partition (open, completed, rejected, in service, deferred);
- the current uncertainty rectangle.

A stale or uncertainty-mismatched candidate cannot replace a validated continuation.

## Deadline semantics

`SolverSupervisor` enforces a **measured** wall-clock deadline with hard process termination. That is not a hard guarantee that useful work finishes inside 0.1 s on a cold start. Startup, transfer and parent validation count toward the budget. Timeout, crash, exception, incomplete/partial results and worker restart after timeout are tested.

If the fallback itself is not certified for the current commitments, the controller reports `no_feasible_continuation`. It does not invent an uncertified depot return.

## Implementation invariant (not a theorem)

“Unvalidated candidates do not overwrite the backup” is an engineering invariant of `BackupStore`. It is not a recursive-feasibility theorem for the closed loop.
