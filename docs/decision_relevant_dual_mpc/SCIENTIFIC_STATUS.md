# Scientific status (foundation repair)

**Branch:** `research/decision-relevant-dual-mpc`  
**Prior tip reviewed:** `93fd812`  
**This repair wave:** nonanticipative 2-EV oracle, REUB_v0 invalidation + REUB_v1, separated baselines, fair unpruned ablation.

## Current verdict: **CORRECTED PROTOTYPE — FOUNDATIONS UNDER REPAIR**

Not a top-tier claim. Not a topic switch. Not ready for large EVRP-TW-D / Amazon campaigns.

### Established in this tip

1. **Nonanticipative two-EV oracle** (`fleet_oracle.py`): history-indexed EV2 policy in `{DIRECT, CHARGE, SKIP}`; EV2 synced to EV1 observation clock `T_obs` before using the posterior; `EXACT_OPTIMUM` only within this finite policy class.
2. **Reverse-ranking regression:** clairvoyant per-θ max ≠ nonanticipative common action value.
3. **REUB_v0 (direct-only) INVALID:** charging counterexample where `v0 < Q*`.
4. **REUB_v1:** optimistic charge-envelope resource bound for the declared single-EV `{A,C,S}` family; verified `≥ Q*` on the toy actions; **not** certified by calling clairvoyant DRUB as a fallback.
5. **Baselines separated:** robust (fixed uncertainty / worst-case, forced prior), optimized passive (forced-prior selection), exact dual, DRUB pruning, info-gain heuristic — each with its own selection score; true Bayes value reported for decision-quality comparison.
6. **Fair unpruned search:** `use_pruning=False` computes **no** unused bounds.
7. **EVRP semantics regressions:** announce→accept→serve, busy/noninterruptible, trajectory replay, commitment completion.

### Not established

- A cheap resource bound that is routinely **tighter** than clairvoyant DRUB **and** cheaper to evaluate on varied networks.
- Scalable computational advantage (toy ms timings remain noisy; heavy-ops gap is small).
- Full event-driven fleet simulator integration / depot-return enforcement in the continuation family.
- Generality beyond hand-built corridor toys.

### Immediate research target (unchanged)

A sound, EVRP-structured information-value upper bound that prunes without requiring the expensive clairvoyant continuation tree on every candidate.

### Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py tests/test_dr_dual_validation.py
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; write_artifacts(Path('docs/decision_relevant_dual_mpc'))"
```
