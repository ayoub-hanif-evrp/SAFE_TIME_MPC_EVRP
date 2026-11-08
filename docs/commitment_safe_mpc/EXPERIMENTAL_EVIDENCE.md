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

## Phase C / B0 (complete; hardened)

| Artifact | Result |
|----------|--------|
| `baseline_comparison.json` | 5/5 both replay-ok; ALNS search on 5/5; improvements on 1/5; **executed_distance** matched insertion (no operational win claimed) |
| Controllers | Insertion vs `ReactiveAlnsMpc` |
| Hardening | Arc-preserving public snapshot; genuine regret-k; sequence-consistent decode; safe `UNKNOWN` failure; cooperative budget |

## Later phases

B1 full-validation witnesses, M1 incremental certificates, Desaulniers / EVRP-TW-D (provenance-valid only) — next after B0 green.
