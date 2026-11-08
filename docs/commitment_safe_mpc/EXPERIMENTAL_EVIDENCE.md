# Experimental evidence

## Phase A (complete)

| Artifact | Result |
|----------|--------|
| `scenario_diagnostics.json` | 4/4 unpruned agree, 4/4 generic agree, 4/4 trajectories ok |
| `docs/decision_relevant_dual_mpc/computational_scaling.json` | Regenerated under aligned policy class; pruning usefulness still not claimed |

## Phase B (complete)

| Artifact | Result |
|----------|--------|
| `phase_b_demo.json` | `all_criteria_met: true` — 2 EVs, dynamic C3/C4, ≥1 charge, multi-replan, commitments fulfilled, replay ok |
| Authoritative plant | `FleetSimulator` + `validation.replay.validate_log` |

## Later phases

Matched B0/B1/M1 tables, Desaulniers / EVRP-TW-D (provenance-valid only), multi-budget incumbents — **not started**.
