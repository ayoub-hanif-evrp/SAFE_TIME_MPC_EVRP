# Problem definition for Part 1

This is the problem the code solves. It is a dynamic, deterministic control problem on top of the Schneider et al. (2014) benchmark. It is not yet a robust-MPC theorem.

## Static benchmark data

An instance supplies:

- one depot
- customers, each with a demand, a hard time window, and a service duration
- charging stations, with no queue capacity in the benchmark
- identical vehicles, with battery capacity `Q`, payload capacity `C`, consumption rate `r`, inverse recharge rate `g`, and speed `v`

For the Schneider files, the deposited readme is authoritative:

- distance is Euclidean
- travel time is distance divided by `v`
- energy is `r` times distance and does not depend on payload
- recharge time is `g` times the energy added

These quantities are benchmark units. They are not claimed to be kilometres or measured kilowatt-hours. Arcs whose energy exceeds `Q` are kept. They are unreachable on a full battery; they are not deleted.

The 2014 operating rule used by the baseline is a full recharge to `Q`. A partial target is a separate policy that uses the same linear rate. Station queues are not simulated.

EVRPTW-ARC road attributes (slope, elevation, traffic, temperature, driving style) are part of the arc record when a file actually contains them. No such file was available. See `docs/datasets/DATA_PROVENANCE.md`. The energy model does not invent kilowatt-hours from those fields.

## Online state

At a decision time the controller may see:

- simulation time
- each vehicle's node, status, state of charge, payload, and onboard customer identities
- the anchor at which the current noninterruptible action will end, if one is in progress
- requests that have been released and are not completed or rejected
- which of those requests are accepted, deferred, or in service

A vehicle status is one of idle, waiting, traveling, serving, or charging.

## Hidden information

Customers in the pool that have not been released are hidden. Their release times exist in the scenario object used by the simulator. They are not fields of `Observation`. The controller is called with an `Observation` only.

Release mechanisms are defined in `safe_time_evrp.evaluation.dynamic`. They do not move a release time to make an offline route feasible.

## Commitments

A released request is announced. The service denominator is the set of announced requests, including rejected ones.

- Deferred: released, but the window opens after the current planning horizon, and the request has not been accepted.
- Accepted: the baseline inserted it while preserving earlier commitments.
- Rejected: the baseline could not insert it without violating physics or an existing commitment. A rejection is not reconsidered.
- In service: service has started and has not finished.
- Completed: service has finished.
- Accepted and unfulfilled: accepted, and still not completed when the episode ends.

Freight for a tour is loaded at the depot. A customer whose goods are onboard is pinned to that vehicle until delivery or a depot reload.

## Uncertainty

Part 1 plans and simulates the nominal energy. `DesignAssumptionEnergyBounds` can label an interval such as `[0.8, 1.2]` times nominal energy. The label says `design_assumption_not_calibrated`. The baseline does not route against that interval. `ScaledNominalEnergy` exists so tests can change the realized factor. It is not a calibration.

## Decision constraints

Travel, service, and charging run to completion once dispatched. Waiting for a closed window is interruptible. The controller may replace only the unexecuted suffix.

The planning horizon is a time length `H`. A released customer who is not yet accepted, and whose window opens after `now + H`, is deferred rather than rejected. An accepted customer is kept in the plan even when the service lies beyond `now + H`. Every constructed route ends with a return to the depot. That return is the terminal condition of the Part 1 baseline. It is not a control-invariant terminal set.

If the constructive planner cannot cover the accepted customers, it first tries the previous feasible suffix. If that suffix also fails from the current anchors, the episode records `no_feasible_continuation` and idle vehicles return to the depot only when that return itself satisfies the battery and the depot deadline. This backup is not a certificate.

## Objective, in priority order

The baseline does not use a weighted sum.

1. Keep a physically feasible suffix under the nominal model.
2. Keep every accepted customer in some vehicle's suffix.
3. Serve as many other announced customers as the insertion heuristic can place.
4. Treat a missed hard window as infeasibility. There is no soft lateness cost.
5. Among feasible insertions, prefer smaller distance and then smaller charge time.

The static Schneider objective, minimize vehicles and then distance for a known customer set, is not the online objective.

## What is intentionally absent

No robust recursive-feasibility theorem, no self-triggered optimal trigger, no solver time budget, no ALNS, and no learned policy. Wall-clock time is measured. It is not a hard timeout.
