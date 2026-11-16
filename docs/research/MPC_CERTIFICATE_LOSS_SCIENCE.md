# Certificate-loss science

Source episodes: `c106C15`, `r103C10`, `r105C15` (see `MPC_CERTIFICATE_LOSS_AUDIT.md`).

## Classification of observed losses

| Code | Meaning | Scientific type |
|---|---|---|
| `travel_timing` | Open-loop plan violates travel time on Validate/replay | **Genuine commitment infeasibility** of scored routes after state advance, or stale suffix after charge/service |
| `impossible_charge` | Charge duration ≠ linear rate model | **Plant/replay semantics mismatch** (F-class model disagreement), not RF preservation |
| `certificate_invalidated_on_recheck` | Advance truncated certificate fails re-Validate | **Certificate-shifting failure** under plant events |
| empty fallback + outstanding accepts | No independently validated backup | **Loss of certified coverage** of \(A_t\) |
| `budget` | Cooperative deadline | **Computation exhaustion** |

## Conclusion for the theoretical claim

A replay-valid trajectory can still lose certified coverage of accepted obligations.
Therefore the controller is **not recursively feasible**.

Correctable pieces:
- Scenario-terminal honesty (fixed: no empty→stochastic cache bleed; no selecting scenario-failed as stochastic).
- Energy-gated charge reduces early anticipatory charge that precedes many `travel_timing` cascades on R instances (diagnostic).

Non-correctable without a stronger terminal-backup theorem:
- Guaranteeing a feasible successor certificate after every plant transition under cooperative budgets.

**Retained property:** certified-emission soundness + scenario-terminal honesty.
**Not claimed:** inductive RF / forward invariance.
