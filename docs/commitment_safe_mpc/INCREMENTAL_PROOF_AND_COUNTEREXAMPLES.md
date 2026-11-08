# Incremental proof sketch and counterexamples

## Proposition (nominal, exact forward prefixes)

Under deterministic nominal linear energy, identical vehicle anchors, and an exact forward resource profile for visit sequence \(v_{1:n}\), if a candidate shares the prefix \(v_{1:k}\) with identical visit objects, then the resource state after position \(k\) equals the stored profile state after \(k\). Feasibility of the candidate then depends only on the suffix \(v_{k+1:n'}\) started from that state (equivalently: full re-evaluation from the anchor yields the same feasibility decision when the prefix and anchors match).

## What is proved in code

Regression tests require agreement of incremental vs full modes on feasible bit, served identities, and distance for supported toy edits. The implementation still calls authoritative `evaluate_route` for the decision (never approx-certifies).

## Counterexamples / falsifiers

1. **Anchor drift:** any change in node/time/SOC/load/onboard invalidates prefix reuse.  
2. **Charge target change** on an otherwise identical charge visit breaks Visit equality → prefix ends earlier.  
3. **Shared station capacity:** not supported by the plant; validators refuse `station_capacity is not None` (`MODEL_CONTRACT_VIOLATED`).  
4. **Locked busy actions:** nonempty suffixes on locked vehicles are contract violations.

## Novelty honesty

Prefix reuse of resource labels is standard in routing/EVRP labeling literature. The investigated distinction is which **MPC events** invalidate which certificates under irreversible commitments — not “we invented concatenation.”
