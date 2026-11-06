# Certificate counterexamples (Part 2.5)

## Counterexample P — fixed-target partial charging

**Plant.** Battery capacity 10, initial SOC 10, velocity 1, consumption rate 1, inverse recharge rate 1, recharge policy `partial`. Depot at the origin. Charger at \((2,0)\). Nominal arc energy 2. Wide windows. Sequence: charge at S to target 8, return to depot.

**Uncertainty.** Travel-time factors `[1, 1]`. Energy factors `[0.5, 2]`. Design assumption, not a confidence interval.

**Upper corner (energy ×2).** Arrival SOC \(= 10 - 4 = 6\). Charge to 8 is allowed. Return is feasible. `evaluate_route` on the scaled instance is feasible. The **pre-repair** upper-corner propagator returned `certified_feasible`.

**Lower corner (energy ×0.5).** Arrival SOC \(= 10 - 1 = 9\). Target 8 is below arrival SOC. `evaluate_route` returns `feasible=False`, `reason=impossible_charge`.

**Conclusion.** Upper-corner feasibility does not imply rectangle feasibility under fixed-target partial charging. Proposition 1 as stated in Part 2 was false for that policy.

**Repair.** `propagate` returns `UNKNOWN` with `fixed_partial_target_not_monotone` when the policy is partial and `energy_lower < energy_upper` and the route contains a charge. Full recharge keeps the exact upper-corner theorem. Degenerate energy bounds (`lower == upper`) keep the exact test for partial as well. No plant policy change.

## Supported combinations (checked)

| Policy | Energy interval | Charge on route | Expected certificate behavior |
| --- | --- | --- | --- |
| full | wide | yes | upper corner exact |
| full | degenerate | yes | upper corner exact |
| partial | wide | yes | `UNKNOWN` |
| partial | degenerate | yes | upper corner exact (same as nominal) |
| either | any | no charge | upper corner exact under A1–A7 for travel/windows |

## Fleet illegalities

Duplicate service of the same customer on two vehicles is `certified_infeasible` / `duplicate_service`. A route keyed by an unknown vehicle id is `illegal_vehicle_assignment`.

## Cache invalidation

Changing the uncertainty rectangle, the anchor clock, or a written charge target invalidates prefix reuse. Interrupted routes with a changed anchor miss the cache.
