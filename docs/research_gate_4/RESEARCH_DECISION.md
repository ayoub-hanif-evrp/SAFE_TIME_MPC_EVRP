# Gate 4 — Research Decision

## Verdict: **NO-GO**

for the proposed contribution  
**“certified / novel marginal commitment-cost MPC for dynamic EVRP.”**

## Why

1. **Theory stop:** Two concrete candidate mechanisms (insertion-displacement opportunity cost; SOC reachability certificates) both reduce to established ADP / resource-extension / stochastic EVRP prior art (Zhang 2023; Jiang et al. 2026; robust reachability). No new sound bound with a quantified novelty claim survived exact toy verification.
2. **Mechanism demonstration:** Exact oracle defines \(\Delta_r\), but no approximation changes the best present action relative to standard stochastic/ADP reasoning in a way that is not already known.
3. **Baseline fairness:** Exploratory Gate 4 diagnostic on preregistered \(\mu\in\{8,15,25\}\) reports **mean `rh_minus_reactive` = 0.0** (24 EVRP-TW-D rows). The Gate 3F 70%-vs-5% gap does not survive the strong reactive baseline under these specs.
4. **Phase C:** Not started — stop criteria forbid implementing another terminal / lookahead controller when the mathematical distinction fails.

## What Gate 4 *did* establish (keep)

| Item | Status |
|------|--------|
| Offline LB / certified UB / exact labels; Gate 3F UB claim withdrawn | Pass |
| Preregistered announcement specs; pooled ready≠λ̂ | Pass |
| Strong reactive baseline vs weak myopic | Pass |
| Blocking plant-advance timing contract + tests | Pass |
| Provenance via `source_commit` + Gate 4 data CI | Pass |
| Exact tiny commitment oracle | Pass |
| Differentiated novel \(\Delta_r\) certificate | **Fail** |

## Infrastructure readiness

The closed-loop testbed is **more trustworthy** after Gate 4 validity repairs. That is necessary but not sufficient for a top-tier algorithmic paper.

## Next (not automatic)

Recommend a **different** MPC hypothesis (or a sharply narrowed theorem with a proof plan that escapes Zhang/Jiang-style ADP), then a new gate. Do **not** begin Part 3. Do **not** implement commitment-cost MPC as a product feature on this evidence.

## Working commands

```bash
python -m pytest -q tests/test_gate4_validity.py
python scripts/run_gate4_diagnostic.py
```
