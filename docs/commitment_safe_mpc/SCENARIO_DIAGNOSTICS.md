# Phase A — D1–D4 scenario diagnostics

**Policy class (shared by exact oracle and online solver):**  
`first_fleet_travel + common_continuation`, `RESTRICTED_CONTINUATION_MAX_LEN = 6`  
(`src/safe_time_evrp/dr_dual/generic/policy_class.py`)

**Artifact:** `scenario_diagnostics.json`  
**Command:** `python -m safe_time_evrp.dr_dual.generic.scenario_diagnostics`

## Root cause of prior 2/4 disagreement

| Factor | Finding |
|--------|---------|
| Different first-action sets | Partially — solver/oracle previously used **primary vehicle only**; D2 omitted v2 travels |
| Planning horizon | **Primary cause** — solver evaluated continuations with `max_len=3` while exact used `max_len=6` |
| Acceptance semantics | Not the disagreement driver on these four |
| Missing charging / terminal | D2/D4 failed under short horizon (no feasible common plan / wrong ranking) |
| Different objectives | Same Bayes reward once horizons matched |

Under `max_len=3`: D1 under-valued multi-customer plans (9.75 vs 14.625 but same first action); D2 returned `None`; D4 ranked exploit over inform. After aligning the declared restricted class: **4/4** unpruned and generic agreement.

## Diagnostic table

| ID | Intent | Feasible first travels (restricted) | Exact optimum (restricted) | Value | Unpruned / generic | Trajectory θ∈{0,1} | Cause (pre-fix) |
|----|--------|--------------------------------------|----------------------------|-------|--------------------|--------------------|-------------------|
| D1_multi_accept | Dynamic announce + remote accept | v1 exploit, v1 inform | `D_N0_exploit` | **14.625** | agree | ok / ok | horizon truncated C1 |
| D2_two_ev | Both vehicles | v1 exploit/inform, **v2 D2_N1**, v2 D2_H0 | **`D2_N1` (v2)** | **17.475** | agree | ok / ok | max_len=3 infeasible; v2 missing from set |
| D3_charge | Necessary charging | v1 exploit, v1 inform | `D_N0_exploit` | **9.65** | agree | ok / ok | none (already agreed) |
| D4_info | Observation-dependent route | v1 exploit, v1 inform | **`D_N0_inform`** | **12.525** | agree | ok / ok | short horizon preferred exploit |

## Independent physical check

For each exact first action, the diagnostic realizes a common continuation under θ=0 and θ=1 and replays the first travel via `replay_plant_log_independent`. All four scenarios: `trajectories_ok = 4/4`.

## Summary (post-fix)

```json
{"n": 4, "unpruned_agree": 4, "generic_agree": 4, "trajectories_ok": 4}
```

Controllers are compared only inside the **same** restricted policy class. Full finite-state event DP remains a separate verification instrument (`event_oracle.py`), not forced into agreement with the restricted class.
