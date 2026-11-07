# Adversarial validation

Primary regressions: `tests/test_dr_dual_urgent_repair.py`  
Also: `tests/test_dr_dual_generic.py` (+ prior repair/advance suites)

| Case | Expected |
|------|----------|
| Five-action C0→C1→depot continuation | ok; \(\mathbb E[R]\approx 14.625\) |
| Legacy TEI vs continuation | legacy value 9.85 **undercounts**; public API `UNSUPPORTED_BOUND` |
| Trivial safe UB | `VALID_BOUND` and ≥ continuation reward |
| ACCEPT without visiting customer | legal after announcement away from node |
| Episode with future releases | `episode_complete` is False while releases pending |
| Restricted oracle label | `EXACT_OPTIMUM_RESTRICTED` (or incomplete statuses) — not full EVRP |
| Search cutoff | never `PROVEN_INFEASIBLE` |
| Optimistic reach state_limit=1 | returns `unknown` |
| Identical histories | identical legal action keys |
| Replay SOC mismatch | `ok=False` |
| No chargers / REUB unsupported | `UNSUPPORTED_BOUND`; solver **forced expand**, never silent discard |
| Model inconsistency (noise) | Travel **committed**; `model_inconsistent`; no belief update |
| Receding-horizon `state=` | Solver uses carried world |
| Discriminating suite | ≥4 structurally distinct nets; two-EV metadata present |

Family OTUB/REUB remain frozen references. Generic TEI is quarantined; trivial safe UB is the temporary certified envelope.
