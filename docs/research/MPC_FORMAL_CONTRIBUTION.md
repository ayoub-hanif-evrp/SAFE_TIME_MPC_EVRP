# Formal MPC contribution (honest)

## Proposed method

**Commitment-Safe Stochastic MPC** — restricted candidate-set stochastic MPC with
B1-validated scenario recourse, transactional certificate emission, and horizon-end
terminal commitment after physically consistent freeze.

## Implemented approximation

| Ideal | Implementation |
|---|---|
| First-stage nonanticipative \(u_t\) | Discrete candidates (ALNS + heuristics + incumbent) |
| Scenario recourse | Shared scenarios; B1-validated causal rollouts |
| Stage-0 hard | `validate_continuation` |
| Terminal hard | `freeze_simulator_at_horizon` + `verify_terminal_commitment` |
| Stochastic terminal | Per-scenario checks; cache keyed by `(FirstActionKey, scenario_set_signature)` |
| Selection | Prefer `STOCHASTIC_TERMINAL`; else explicit `nominal_backup_unchecked` (weaker guarantee) |

## Valid theorem (not recursive feasibility)

**Certified-emission soundness.** Whenever status=`CERTIFIED_FEASIBLE`, independent
Validate covers \(A_t\cup A^{\mathrm{new}}\) for the published routes; speculative
accepts never appear after failed Validate.

**Proposition (scenario-terminal honesty).** A candidate may be labeled
`STOCHASTIC_TERMINAL` only after terminal verification under the declared scenario set.
Empty-future success does not imply scenario success. Scenario-failed candidates are
excluded from the stochastic selection pool.

Unconditional forward invariance of the viable set is **withdrawn** (certificate-loss
audits). See `docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`.

## Principled algorithmic improvement (from diagnosis)

**Energy-gated anticipatory charging.** Diagnosis showed worst R/RC losses begin when
CSS ranks anticipatory charge over serving announced customers while greedy-nominal
serves. Tie-breaks previously preferred charge.

Mechanism: after ranking, if the winner is charge-first and the incumbent is not already
charging, replace it by the best non-charge alternative in the same feasibility class
unless the estimated value advantage clears `charge_advantage_margin` (default 25).
This is an EV opportunity-cost gate, not an arbitrary waiting bonus.

## What is *not* claimed

- Global stochastic optimality
- Recursive feasibility / forward invariance of \(\mathcal{V}\)
- That forecast scenarios alone create the economic gain
