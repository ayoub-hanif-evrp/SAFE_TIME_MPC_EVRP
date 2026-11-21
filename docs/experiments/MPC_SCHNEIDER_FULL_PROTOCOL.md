# Schneider full-instance protocol (`mpc_schneider_full_v1`)

**Scope:** all Schneider instances from `list_schneider_refs()` — families c/r/rc, sizes 5/10/15/100 (92 stems).

**Realizations:** 2 on small (C5/C10/C15); 1 on 100-customer (every stem still covered).

**Proposed:** recovery forecast stack + M1–M4 + stratified scenarios + adaptive compute; `selection_mode=mean_score`.

**Baseline:** greedy-nominal CCE.

**Metrics (per cell, both controllers):**
- economic \(J = 100\cdot\)completed \(-250\cdot\)AU \(-\) distance
- completed_count, service_rate, AU, rejects
- executed_distance, executed_charge_time, charged_energy, n_charge_starts
- makespan, wall/optimize/simulation seconds, decide latency

**Speed:** `--workers N` ProcessPool over independent cells (default 8). Same math as serial; only wall-clock changes.

**Outputs:** `MPC_SCHNEIDER_FULL_RESULTS.{json,md}`

**Hanif A/B:** deferred (next campaign).

