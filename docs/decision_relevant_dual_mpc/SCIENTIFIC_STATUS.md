# Scientific status

**Branch:** `research/decision-relevant-dual-mpc`  
**Cycle:** Refocus → commitment-safe / computation-aware MPC for D-EVRP (Phase A complete)

Primary scope document: `docs/commitment_safe_mpc/RESEARCH_SCOPE.md`

## Verdict: **NOT YET SUBSTANTIVE** for the paper claim — Phase A CI + D1–D4 policy-class alignment done; dual-bound pruning remains unsupported

### What holds after repair

1. Legacy TEI bound **quarantined**; five-action counterexample reproduced (14.625 vs 9.85).
2. Trivial safe reward UB certified for temporary use (`VALID_BOUND` only when optimistic by construction).
3. Oracle statuses distinguish restricted vs full finite search; cutoffs ≠ infeasibility proofs.
4. Fleet-level ACCEPT; closed-loop awaits future releases; depot contract in `episode_complete`.
5. Discriminating suite D1–D4 replaces degenerate 8×9.75 as the development experiment.

### What remains open

- Tight repaired TEI / resource bound on the corrected model.
- Exhaustive event oracle at useful sizes with full busy-interval event queue.
- Computational usefulness of any bound (prior screen failed; do not claim acceleration).
- Top-tier paper claim (anytime information-aware MPC) — aspirational only.

### Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py tests/test_dr_dual_validation.py tests/test_dr_dual_advance.py tests/test_dr_dual_generic.py tests/test_dr_dual_urgent_repair.py
python -m safe_time_evrp.dr_dual.generic.compute_scaling
```

See `URGENT_CORRECTNESS_REPAIR.md` and `PAPER_CONTRIBUTION_DECISION.md`.
