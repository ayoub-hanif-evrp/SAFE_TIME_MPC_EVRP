# Phase 3E — Baseline fairness contract

**Finding: `EQUIVALENT_TO_STOCHASTIC_ROLLOUT`**

Artifacts: [`phase3e_decision_traces.json`](phase3e_decision_traces.json), [`phase3e_matched_results.json`](phase3e_matched_results.json)

## Defect repaired

In the accelerated / repaired development pilot, `stochastic_uniform` used ALNS `seed` while `proposed_mpc` used `seed + 1`. Those seeds change ALNS candidate generation. Separately, `CommitmentSafePredictiveMpc.allocation` is recorded in notes/audit but **does not** change candidate generation, scenario construction, or argmax.

Therefore any proposed-versus-stochastic “win” under mismatched seeds was not evidence of a distinct allocation mechanism.

## Matched-decision contract

Both predictive controllers now share:

| Contract item | Status |
|---------------|--------|
| Same public observation | yes |
| Same candidate set and order (matched ALNS seed) | yes |
| Same forecast scenarios and probabilities | yes |
| Same recourse (`b1_validated`) | yes |
| Same score definition | yes |
| Same evaluation seed | yes |
| Same ALNS time / iteration budget | yes |

Under that contract, `proposed_mpc` and `stochastic_uniform` are **algorithmically identical**: identical argmax over identical rollouts.

## Empirical confirmation

On the Phase 3E matched grid (`A_dense_arrivals`, `A_low_soc_charge`, `B_easy_dynamic` × seeds `{3,7,11}`):

- `n_valid_cells = 9`
- `stoch_equals_proposed_valid = 9`

No valid cell shows a proposed-versus-stochastic difference in completed service, accepted-unfulfilled, or executed distance.

## Implication

Do **not** claim a proposed-MPC win over standard stochastic rollout from the repaired Phase 3D six-case table. The scientifically honest label for that comparison is **`EQUIVALENT_TO_STOCHASTIC_ROLLOUT`**. Remaining questions are about stochastic rollout (including its shared predictive machinery) versus reactive B1/M1 under matched resources.
