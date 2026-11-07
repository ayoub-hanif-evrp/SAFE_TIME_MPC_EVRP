# Gate 3E — Closed loop and commitments

## Termination

An episode is finished only when:

1. No `request_release` remains scheduled at or before `t_max`, and
2. No open announced/accepted/deferred/in-service requests remain, and
3. No further plant events are due within `t_max` (or the fleet is idle at depot with an empty event queue in horizon).

Staggered arrivals (A at 0, B at 20) must process B.

## Commitment accounting

- **Physical feasibility:** independent replay of the event log.
- **Nominal commitment feasibility:** cleaned routes must cover all accepted (not completed) customers via `evaluate_route` before admission.
- Accepted customers are never reclassified as rejected.
- At cutoff, unresolved accepted obligations are reported as `accepted_unfulfilled`.

## solomon_140 RH trace (Gate 3E harness)

Under SHA-256 release/forecast seeds and the commitment gate:

- Served: 4
- Commitment violations: 0
- Replay OK: true

(Gate 3D had reported 0 served / 4 violations on a privileged-forecast protocol — not comparable as the same experiment.)

## Computation time

Optimizer wall time is recorded. Optional `advance_plant_during_optimize` exists but is **off** by default; Gate 3E does **not** claim hard real-time / deadline-aware physical execution until that contract is enabled and tested under overlapping events.
