# Incremental continuation-certificate formulation

Status: **research target — not claimed.**

A **physically feasible continuation witness** for accepted commitments: executable route/charging suffixes with explicit safety assumptions (robust under a declared disturbance set, or labeled probabilistic).

## Intended MPC steps

Observe → preserve/update witness → evaluate new commitments → identify time-critical decisions → improve plan with ALNS retaining validated incumbent → interrupt safely → execute and replan.

## Mathematical targets (to prove or falsify)

- **Prop A:** safety of incumbent first-action execution  
- **Prop B:** sound incremental revalidation ≡ full validation inside certificate class  
- **Prop C:** EVRP-specific work bound on affected dependency region  

Generic “anytime retains best feasible incumbent” is **not** novelty. Compare against fixed-route rectangular certificates and established warm-start / safe anytime MPC. Acknowledge equivalence if it appears.
