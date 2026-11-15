# MPC terminal feasibility validation

## Predicate separation

| Check | Module | Meaning |
|---|---|---|
| Stage-0 commitment | `validate_continuation` | Covers obligations **now** |
| Horizon-end terminal | `project_to_horizon` + `verify_terminal_commitment` | Feasible suffix at horizon end |

## Rejection taxonomy

- `terminal_infeasible` — terminal state not in X_f
- `rollout_failed` / `replay_failed` — projection invalid
- `budget` — cooperative deadline during projection

## Gate-2 evidence

Automated tests in `tests/test_css_mpc_gates_1_to_4.py`:

- `test_gate2_verify_terminal_rejects_stranded_obligation`
- `test_gate2_stage0_pass_terminal_constraint_is_distinct`

Constructed stranded terminal states with insufficient SoC fail `verify_terminal_commitment` even when a healthy stage-0 full route on a different start state is evaluated separately.

## Controller integration

`CommitmentSafeStochasticMpc._terminal_filter` rejects candidates that fail terminal checks on any scored scenario before soft objective ranking.
