# Hanif / Homberger A+B latency protocol (`mpc_hanif_latency_ab_v1`)

**Budget box:** ≤ 2 hours wall.  
**Claim type:** large-scale **decision latency / stability** (not full closed-loop \(J\) ranking — closed-loop 1000-customer stalls under cooperative budget).

## Scope

| Block | Coverage | Bench |
|---|---|---|
| **Primary** | all **120** files: variant A (60) + B (60) | timed `decide()` × 5, announced-cap **25** |
| **Curve** | stratified **12** files (1 per family × 6 families × A/B) | caps **{25,50,100,200}**, same timed bench |

## Controllers

- **Proposed:** recovery M1–M4 stack, `selection_mode=mean_score`, stratified + adaptive, **`use_forecast=False`** (no Hanif-fit prior; do not transfer Schneider forecasts).
- **Baseline:** greedy-nominal CCE.
- Decide budget: **2.0 s** (Homberger latency target from prior PASS).

## Pass rules

1. **0 hard decide failures** on primary A+B.  
2. Proposed p50 decide time **≤ 2.0 s** on primary (report A, B, pooled).  
3. Curve: no hard fails; report p50 vs cap (scalability shape).

## Outputs

- `MPC_HANIF_LATENCY_AB_RESULTS.{json,md}`
- `MPC_HANIF_LATENCY_AB_SPLITS.json` (frozen file lists)
