# Exact toy cases

Module: `safe_time_evrp.optimization.exact_toy`.

The enumerator assigns each customer to a vehicle or to the unserved set, tries every order, and tries every pattern with at most one full recharge in each gap (before a customer or before the return). Waiting is only the benchmark wait for a closed window. There is no solver timeout because the family is finite. If a route is outside the family, the label does not apply.

Labels used in code:

- The best served count, distance, and charge time are proved only inside the family.
- `heuristic_matches_proven_optimum` means the insertion heuristic served the same customers' count and matched the distance.
- `heuristic_feasible_service_count_matches` means the counts match and the distance need not.
- `heuristic_missed_a_proven_feasible_route` means the family contains a route and the heuristic served nobody.
- `proven_feasible` and `proven_infeasible` on `forced_first_travel` refer to continuations after one forced departure, still inside the family.

## Cases that the test runs

`easy`. Battery 50, three customers, one charger, two vehicles. The family serves all three. The heuristic also serves three.

`needs_two_charges`. Battery 25, depot at 0, charger at 10, customer at 20, rate 1. A direct trip does not leave enough energy to reach a charger afterward. The family finds a route that recharges before the customer and again before the return, so `feasible_exists` is true and `best_served` is 1. The insertion heuristic, which adds at most one recharge beside the inserted customer, serves nobody. That is an explicit heuristic miss, not a proof that the customer is infeasible.

`forced_first_travel("needs_two_charges", "C1", "C1")` is `proven_infeasible`: leaving toward the customer first destroys the continuation in this family. `forced_first_travel("needs_two_charges", "C1", "S")` is `proven_feasible`.

`impossible_window`. `C1` is 10 time units away and the window closes at time 1. The family serves only `C2`. Traveling to `C1` first is `proven_infeasible`. The heuristic also serves one customer.

These labels must not be copied onto `c101_21` or any instance that was not enumerated.
