# Scientific status

**Branch:** `research/decision-relevant-dual-mpc`  
**Cycle:** Generic finite-state EVRP–MPC + TEI bound + frozen scaling study

## Verdict: **NOT YET SUBSTANTIVE** (pruning hypothesis fails compute screen)

### What holds

1. P0 fixes: bound statuses (`VALID` / `UNSUPPORTED` / `PROVEN_INFEASIBLE` / `UNKNOWN`); unsupported never silently discards; commit-then-fail model inconsistency; RH `state=`; hardened replay.
2. Generic finite-state reference (1–2 EVs, 3–5 customers, announcements, depot contract) with exact finite-policy optimum label.
3. Generic TEI resource bound with proof sketch + adversarial tests.
4. Frozen 8-instance scaling suite: **8/8** exact first-action agreement under generic pruning.

### What fails the paper bar

- **0/8** heavy-op improvements from pruning.
- Median wall-time reduction ≈ **0.3%** (screening target 20–30% **not met**).
- No differentiated computational contribution beyond classical information-relaxation ideas.

### Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py tests/test_dr_dual_validation.py tests/test_dr_dual_advance.py tests/test_dr_dual_generic.py
python -m safe_time_evrp.dr_dual.generic.compute_scaling
```

See `PAPER_CONTRIBUTION_DECISION.md`.
