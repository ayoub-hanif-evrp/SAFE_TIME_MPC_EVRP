# Counterexamples and exact checks

Each case names the plant and the rectangle. "Proved" means Proposition 1 applied to a fixed sequence, or an independent call to `evaluate_route` on arc tables scaled to a concrete factor. None of these cases is a statistical claim.

## Case A — energy margin removed by an insertion

Plant: battery 40, consumption rate 1, velocity 1, depot at the origin, customer A at \((10,0)\), customer B at \((10,10)\), windows wide. Rectangle: time and energy factors \([1, 1.3]\).

The direct route depot–A–depot uses nominal energy 20 and worst-case energy 26. Proposition 1 certifies it. The insertion depot–B–A–depot has nominal length about 34.1, so `evaluate_route` accepts it, and worst-case energy about 44.4, so the certificate returns `certified_infeasible` with `battery_floor`. The independent scaled-arc check agrees. The controller must not replace the direct backup with that insertion.

## Case B — window destroyed by travel-time uncertainty

Same geometry except A is due at time 25, B is at \((3,4)\), and the battery is 100. The rectangle has time factor \([1, 2]\) and energy factor 1.

The detour depot–B–A is nominally inside the window (travel time about 13.1). At the upper time factor the arrival is after time 25. The certificate returns `missed_window`. A controller that accepts the detour because the nominal distance improved has broken the commitment.

## Case C — solver timeout

The worker is asked to sleep 30 s. The deadline is 0.4 s. The supervisor returns `timeout`, the process is terminated, and a pre-existing backup object is left at its old version. This tests preemption. It does not test a useful optimization, because the worker never starts one.

## Case D — stale action identity

A candidate is staged against an idle vehicle at the depot. `commit` is then called with a traveling vehicle that has a locked destination. The action identity differs, `commit` returns false, and the backup version stays 0. A second proposal against the original observation can still be committed. A late result does not move the backup.

## Case E — conservative tightening

Battery 30, customer A at distance 10, factors \([1, 1.2]\). Worst-case energy of depot–A–depot is 24, which is feasible. The same propagator with energy inflation 1.5 uses factor 1.8 and energy 36, and returns `certified_infeasible`. The model field is `tightened_rectangle`. The gap is intentional: the inflated test is sufficient for a harder set and is not necessary for the original rectangle. The exact mode is what Propositions 1–3 talk about.

## Case F — trigger counts

On the easy toy (battery 50, three customers, factors \([1, 1.05]\)), the validity-aware policy does not optimize on arrival, service completion, or the timer unless an announcement is still unanswered. The every-event policy does. The unit test requires fewer validity-aware optimizations and completion of all three customers. A flag that also ignores releases does not optimize on `request_release`. That flag is a counterexample to "skipping solves is always safe," not a controller.

The process-isolated pilot, deadline 5 s, served all three customers under B0, B1, fixed period (6 solves), every event (15 solves), slack (4 solves), and validity-aware (4 solves). Every robust run except fixed period discarded one stale candidate. There were no commitment failures and no timeouts at that deadline. This is one run.

## Case G — no continuation

Battery 5 and customer A at distance 10. The only route that serves A fails `battery_floor` at factor 1. The controller's decision has `no_feasible_continuation`, an empty route, and backup version 0. It does not emit a depot return that the certificate did not accept. There is no safe fallback to invent: the empty plan does not serve A, and the episode can end as `accepted_unfulfilled` if A was already accepted.

## Case H — outside the contract

Battery 30, factors \([1, 1.1]\), direct service of A. The upper corner uses energy 22 and is certified. A realization with energy factor 2 is not in the rectangle. `evaluate_route` on that scaled instance returns `battery_depleted`. The certificate is not edited after the fact. The guarantee failed because the assumption failed.

## Shift check

For the route of Case A’s direct service, the first arc is realized at the nominal factor and the return is re-certified at the upper factor. The suffix is feasible, as Proposition 2 requires. This is one route, not an enumeration of every toy.

## Non-monotone flag

The same direct route with `monotone_linear=False` returns `unknown`, not `certified_infeasible`.

## Replay

Part 1 replay tests still pass after the zero-duration charge skip. Part 2 did not point the certificate at the replay module, and the replay module does not call the certificate.
