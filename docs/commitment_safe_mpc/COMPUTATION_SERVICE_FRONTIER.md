# Computation–service frontier (development)

Protocol: matched Insertion / B0 / B1 / M1 (+ ablations) under several cooperative `time_limit_seconds` values on the frozen baseline suite plus scaled 12–28 customer cases.

## Axes

- X: CPU/wall optimize seconds (or budget knob)  
- Y: completed customers / executed distance / certified decisions  

## Current development reading

Request-rescue enables coverage improvements the constructor alone misses (packing fixture). On the original five tiny cases, insertion/B0/B1 often remain tied on completed sets. Outer validation remains a small fraction of optimize time; inner `evaluate_route` dominates.

M1’s value, if any, must appear as equal-or-better service at equal budget with fewer redundant evals — evidence lives in `baseline_comparison_m1_ablation.json` and `compute_bottleneck_profile.json`. No automatic claim of dominance.
