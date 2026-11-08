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

## Phase D / B1 (complete)

| Artifact | Result |
|----------|--------|
| `baseline_comparison_b0_b1.json` | Insertion/B0/B1: 5/5 replay-ok; executed distances matched; B1 certifies feasible decisions |
| `B1_CORRECTNESS_RESULTS.md` | Accept-after-validate; adversarial commitment-break refused by validator |
| `revalidation_cost_profile.json` / `REVALIDATION_COST_PROFILE.md` | Redundant full rechecks measured for future M1 |

## Request-rescue + M1 (development)

| Artifact | Result |
|----------|--------|
| `ALNS_REQUEST_RESCUE.md` / rescue tests | Constructor `{A,B}` → ALNS recovers `{A,B,C}` |
| `compute_bottleneck_profile.json` | Inner route eval dominates outer B1 validation |
| `baseline_comparison_m1_ablation.json` | Insertion/B0/B1/M1 (+2 ablations) matched study |
| `budget_frontier.json` / `COMPUTATION_SERVICE_FRONTIER.md` | Priority-7: 285 runs on 10–50 cust; M1 faster 13/15 vs B1, service win 2/15 |
| Scientific claim | **Not established** — see `SCIENTIFIC_VERDICT.md` |
