# Adversarial validation

Tests: `tests/test_dr_dual_generic.py` (+ prior repair/advance suites)

| Case | Expected |
|------|----------|
| No chargers / REUB unsupported | `UNSUPPORTED_BOUND`; solver **forced expand**, never silent discard |
| Model inconsistency (noise) | Travel **committed**; `model_inconsistent` on state; no belief update |
| Receding-horizon `state=` | Solver uses carried world, not cold-start only |
| Replay SOC/time mismatch | `ok=False` |
| Accept before observation | ACCEPT then TRAVEL legal |
| Generic bound vs \(Q^\star\) | When `VALID_BOUND`, value ≥ exact Bayes first-action value |
| Frozen suite variety | ≥2 distinct customer counts; 8 seeded instances |

Family OTUB/REUB remain frozen references; generic bound is the candidate for general pruning.
