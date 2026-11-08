# Computational bottleneck profile (updated)

Outer B1 continuation validation is cheap on the development toys. The dominant cost is **candidate `evaluate_route` work inside ALNS decode/repair**.

Artifact: `compute_bottleneck_profile.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.compute_profile`

## What is measured

- Route evaluations and ALNS candidates/iterations  
- Validation seconds (B1 per-decision increments)  
- First/best feasible incumbent times and time after best incumbent  
- Rescued-customer counts  
- Scaled 12/20/28-customer cases plus rescue packing case  

## Implication for M1

Caching only the final B1 check is insufficient. M1 targets:

1. Exact incremental route-resource evaluation inside ALNS  
2. Event-aware certificate retention across MPC epochs  

See `INCREMENTAL_RESOURCE_CERTIFICATE.md` and `M1_ALGORITHM.md`.
