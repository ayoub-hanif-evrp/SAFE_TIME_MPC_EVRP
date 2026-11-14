# Root cause of MPC underserving

**Branch tip:** see latest push SHA  
**Prior reviewed commit:** `ecab5a8`  
**Primary verdict after diagnosis:** **IMPLEMENTATION_DEFECT_CONFIRMED** (fixed) + residual **OBJECTIVE_MISSPECIFICATION** / mixed closed-loop **REVISE**

Artifacts: [`root_cause_trace.json`](root_cause_trace.json), [`ROLL_OUT_REPLAY_CONTRACT.md`](ROLL_OUT_REPLAY_CONTRACT.md), [`repaired_development_results.json`](repaired_development_results.json)  
Archived pre-repair smoke JSON: [`accelerated_results_ecab5a8_smoke2_ARCHIVE.json`](accelerated_results_ecab5a8_smoke2_ARCHIVE.json)

## P0 — Hypothesis test

**Suspected defect:** `seed_simulator_from_observation()` restored public request statuses without logging historical `request_release` events. Independent `validate_log` then raised `early_request_access` on any accept/reject of already-visible customers, and rollouts scored `-1e9`.

**Reproduction (pre-fix):** on `B_phase_b` / `B_tight_battery`, forked accept of announced `C1` → `replay_ok=False`, `code=early_request_access`.

**Conclusion:** **IMPLEMENTATION_DEFECT_CONFIRMED.** This alone can explain controllers preferring idle/reject over serve when serve candidates are artificially poisoned.

## P1 — Fix applied

Fork now emits decision-epoch snapshot `request_release` records for all *already public* customers (`source=decision_epoch_snapshot`), plus `vehicle_init`, and busy-action remainder `depart`/`service_start`/`charge_start` evidence. Hidden customers still fail replay.

Regression: `tests/test_root_cause_fork_replay.py`.

## P2 — Fail-closed scoring

`expected_rollout_value()` no longer averages only valid scenarios. **Any** invalid scenario → candidate value `-1e9`.

## P3 — Action generator

- `wait_idle` / charge no longer auto-reject announcements.  
- Explicit reject actions remain labeled rejects.  
- B1 action included in the counterfactual set.  
- Tie-break prefers new accepts / service first-legs over `wait_idle`.

## P4 — Artifact workflow

- Unit tests write only to `tmp_path`.  
- Pre-repair tracked 2-case JSON archived.  
- Full 6-case repaired pilot written to `repaired_development_results.json` (cases and report agree).

## P5 — CI on `ecab5a8`

GitHub Actions failed in **Download and verify public benchmarks** with `metadata_request_failed` (external Zenodo/Mendeley metadata). Lint/pytest were **skipped**, not failed. Local pytest was green. This is an infrastructure/network status, not evidence against the MPC diagnosis.

## Post-repair first-epoch traces

On `B_phase_b` and `B_tight_battery`, after the fork fix + tie-break:

- Serve/accept candidates are **replay-valid** (no `early_request_access`).  
- Chosen first action **matches B1** (ALNS/B1 first leg).  
- Overall first-epoch label: **OBJECTIVE_MISSPECIFICATION** / later closed-loop effects — not a remaining false `-1e9` poison at epoch 0.

## Post-repair 6-case matched pilot

From `repaired_development_results.json`:

| Metric | Value |
|--------|------:|
| Cases | 6 |
| Wins vs B1 | 1 |
| Losses vs B1 | 1 |
| Wins vs identical-candidate stochastic | 1 |
| Verdict | **REVISE** |

The earlier “six losses / NO-GO” claim from `ecab5a8` Markdown is **not trusted as scientific fact** until this repaired artifact; the committed smoke JSON had only two cases.

## Coexisting cause labels

1. **IMPLEMENTATION_DEFECT_CONFIRMED** — false `early_request_access` (fixed).  
2. **OBJECTIVE_MISSPECIFICATION** — equal-valued wait vs serve tie-break preferred idle (fixed); residual scoring / horizon value may still mis-rank later epochs.  
3. **GENUINE_POLICY_FAILURE** — not established as the sole pre-repair explanation; post-repair closed-loop is mixed (**REVISE**), not a clean six-loss NO-GO.

## What not to conclude yet

Do not claim top-tier novelty or abandon commitment-safe predictive MPC. Next: inspect closed-loop epochs *after* the first decision where proposed still diverges from B1 under **valid** scores, then reformulate the objective only with independent score audits.
