# Certificate specification

## Entry point

```python
certificate = certify(
    observed_state=observation,
    committed_routes=routes,
    uncertainty_set=uncertainty,
    instance=instance,
)
```

`certify` lives in `safe_time_evrp.robust.certificate`. The instance is an argument because the observation deliberately does not carry the network.

## Return value

| Field | Meaning |
| --- | --- |
| `verdict` | `certified_feasible`, `certified_infeasible`, or `unknown` |
| `assumptions` | The rectangle, the evidence class, and any extra inflation |
| `validity` | Sequence fixed, factors inside the rectangle, linear charge, nominal payload and service |
| `energy_margin` | Smallest state-of-charge slack above the floor on the upper corner. `None` if unknown |
| `time_margin` | Smallest window or depot slack on the upper corner. `None` if unknown |
| `critical_constraint` | `ok`, or the first proved failure (`battery_floor`, `missed_window`, `commitment_omitted`, ...) |
| `runtime_seconds` | Wall time of this call |
| `witness` | Node, time, state of charge, or the missing customer |
| `model` | `schneider_linear_rectangle`, or `tightened_rectangle` if an inflation factor above 1 is applied |

`certified_infeasible` is used only when the upper-corner simulation itself fails, when an arc does not exist, or when an accepted customer is absent from the sequences. A search that finds no insertion returns no verdict of infeasibility. The controller then keeps the backup and, if the backup does not cover the commitments, reports `no_feasible_continuation`.

## Supported check

For a fixed visit list the propagator walks the upper time factor and the upper energy factor on every arc. It uses the same loading, window, full-charge, and depot-return rules as `environment/physics.py`, but it does not call that function. An independent check builds a copy of the instance whose arc tables are scaled to the same corner and calls `evaluate_route`. The tests require the two answers to agree.

The upper corner is necessary and sufficient only under the assumptions in `FEASIBILITY_PROOFS.md`. With an energy inflation above one, the same code is only a sufficient test. Case E is that gap: inflation 1.5 rejects a route the exact rectangle accepts.

If `monotone_linear` is false, or a partial charge has no target, the verdict is `unknown`.

## Fleet plan

Every accepted customer must appear as a service visit. A battery-feasible route that drops an accepted customer is `certified_infeasible` with `commitment_omitted`. Announced customers are not required.

## Incremental prefix

`propagate_incremental` reuses the stored upper-corner state at the longest unchanged prefix and resimulates the suffix. On the checked example it matches a full propagation. It was not faster in any sense that would matter, and it is a standard prefix cache. It is not part of the novelty claim.

## What this object is not

It is not a certificate that some other sequence could serve the customers. It is not a proof that the next optimizer call will succeed. It is not valid for station queues, time-dependent speeds, or a disturbance outside the factors.
