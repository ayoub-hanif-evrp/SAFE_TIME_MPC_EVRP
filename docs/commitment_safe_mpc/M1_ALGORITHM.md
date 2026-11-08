# M1 — Certificate-carrying ALNS–MPC

Controller: `CertificateCarryingAlnsMpc` (`m1_mpc.py`)

## Composition

1. Same `ReactiveAlnsMpc` engine as B0 (including request-rescue).  
2. Inner-loop `EvalMode.INCREMENTAL_EVALUATION` (ablation: full eval).  
3. `CertificateStore` for cross-event retention (ablation: disabled).  
4. B1-style `validate_continuation` admission gate before accepts.  

## Per epoch

1. Public snapshot only.  
2. Optionally advance/revalidate prior certificate under exact-anchor compatibility.  
3. Run ALNS under cooperative budget.  
4. Independently validate candidate; accept new customers only if commitments ∪ {new} certify.  
5. Publish certificate on success; retain best validated incumbent.  

Statuses: `CERTIFIED_FEASIBLE` | `UNKNOWN` | `MODEL_CONTRACT_VIOLATED`.

## Not claimed

Robust recursive feasibility; hard real-time preemption; shared-charger capacity; paper-ready superiority on Schneider-scale fleets.
