# Deterministic event-triggered MPC baseline

Implemented in `safe_time_evrp.controllers.mpc` and `safe_time_evrp.controllers.episode`. The route construction is `safe_time_evrp.optimization.insertion`. This is a working receding-horizon controller. It is not a research claim.

## State

`Observation` is the controller input. For each vehicle it contains the current physical state and an anchor. The anchor is the predicted state at the end of travel, service, or charging. Idle and waiting vehicles use the current state as the anchor.

## Horizon and terminal condition

The horizon is the configuration value `horizon` (1236 time units in the development scenario, equal to the `c101C5` depot deadline).

`construct_routes` inserts accepted customers first, even if their ready time is greater than `now + horizon`. In that case `horizon_extended` is true. Other released customers whose windows open after `now + horizon` are deferred.

`evaluate_route` appends a depot return when the suffix does not already end there. A route that cannot return inside the depot window, or that would arrive with a negative battery, is infeasible. Accepted customers are not dropped to make the horizon shorter.

## Optimization

At each decision the planner rebuilds suffixes from the anchors.

For each customer, in order of due date and then identifier, it tries every idle-or-busy vehicle that is allowed to carry that customer, every insertion index, and these local edits:

- direct insertion
- one full recharge immediately before or after the customer, at each station
- a depot reload before the customer, with or without one recharge

The feasible edit with the smallest distance, then the smallest charge time, then the smallest vehicle identifier and index, is kept. Pinned onboard customers can be inserted only on their vehicle.

This is greedy. On the toy `needs_two_charges` the enumerated family finds a feasible route with two recharges, and this heuristic does not. The outcome is recorded as `heuristic_missed_a_proven_feasible_route`.

## First action

`FleetSimulator.apply_decision` does not restart a vehicle whose status is traveling, serving, or charging. It stores the new suffix and leaves the current action in place.

For an idle or waiting vehicle it executes only the first visit:

- travel, if the visit is elsewhere
- service, charge, or reload, if the vehicle is already at that node
- a depot return, if that is the first visit

Freight for the customers before the next depot visit is loaded when the vehicle is at the depot. The development log shows this as `load_freight` immediately before `depart`.

## Triggers

The episode loop calls the controller on:

- `request_release`
- `arrive`
- `service_end`
- `charge_end`
- `wait_end`
- `replan_interval` at `now + max_replan_interval`
- an initial call at time 0 when the first event is strictly later

Simultaneous releases are processed in schedule order, one decision each. The development scenario uses `indexed_stagger`: sorted customer ids at times `0, step, 2 step, ...`. The step does not depend on a reference route.

## Commitments and fallback

New customers are accepted only when a feasible insertion exists after all current commitments have been placed. Otherwise they are rejected.

If commitments themselves cannot be placed, `EventTriggeredMPC` re-evaluates the previous suffix from the current anchors. When that suffix is feasible and still covers every accepted customer, `fallback_used` is true and no new rejection is issued.

When the previous suffix also fails, `no_feasible_continuation` is true. Idle vehicles receive a depot return only if `evaluate_route` says that return is feasible. The note on the decision is `safe_return_is_a_heuristic_backup_not_a_certificate`.

## Timing

`Decision.optimize_seconds` is the wall-clock duration of `decide`, measured with `time.perf_counter`. `EpisodeResult.simulation_seconds` is the rest of the episode wall clock. Neither value stops the process at a deadline.

## Development episode

Instance `c101C5`, two vehicles, horizon 1236, replan interval 200, stagger step 40. The independent replay accepted the log. Three of the five announced customers were completed (`C100`, `C12`, `C85`). `C30` and `C64` were rejected. There were 20 decisions, zero fallbacks, and zero `no_feasible_continuation` flags. Total optimization time on the machine that produced `experiments/development/c101C5/run_manifest.json` was about 2.3 ms. That file is local and is not committed.

At time 0, `v1` loaded freight and departed for `C100`. The arrival at time 38.08 matched that destination. The request at time 40 was assigned to `v2`. The travel already in progress was not given a new destination.
