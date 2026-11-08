# Scientific verdict

**Current:** Phase A–C complete; B0 hardened; **B1 full-validation MPC implemented**.  
**Paper claim:** **NOT YET** — B1 is the safe baseline, not the contribution; no incremental-certificate theorem (M1).

### What is established

- Quarantined invalid TEI; honest restricted oracle labels.  
- D1–D4 aligned under a declared shared restricted policy class (4/4).  
- Authoritative `FleetSimulator` plant + independent replay; Phase B demo criteria all met.  
- Public planning snapshot with **arc-preserving** sanitization (no unreleased customer leak).  
- Reactive ALNS–MPC (B0): genuine regret-k, sequence-consistent decode, cooperative budget, safe `UNKNOWN` failure; 5/5 matched replay-ok vs insertion on **executed** distance.  
- Full-validation ALNS–MPC (B1): same ALNS engine + independent `validate_continuation`; accept-after-validate; incumbent revalidation; 5/5 replay-ok; adversarial refusal of commitment-breaking extras.  
- Revalidation cost profile logged for future M1 (measure only).

### Audit answers (Commit-2)

1. **CI green including smoke?** Yes — ruff, pytest, `smoke_test`, clean import of `controllers.episode`, baseline compare.  
2. **Distinct operators?** Yes — greedy vs genuine regret-2/3; repair ops retained only as real selectors.  
3. **Executed costs?** Yes — `executed_distance` from depart arcs; planned sum is diagnostic only; no 3.5% operational-improvement claim.  
4. **Arc preservation?** Yes — public snapshot filters original arcs; regression for asymmetric weights.  
5. **Safe B0 failure?** Yes — empty / verified-only returns; status `UNKNOWN`, never proven-infeasible.  
6. **B1 same engine?** Yes — `FullValidationAlnsMpc` composes `ReactiveAlnsMpc`.  
7. **Accept-after-validate?** Yes — `newly_accepted` only after `validate_continuation` succeeds.  
8. **Incumbent revalidation?** Yes — previous witness rechecked against current anchors before reuse.  
9. **Validation overhead?** Measured in `validation_seconds` / `REVALIDATION_COST_PROFILE.md` (small on toys; redundant work catalogued).  
10. **M1 target work?** Redundant full rechecks of unchanged obligations, idle routes, repeated charge checks, double validation on rejected new accepts — **no M1 code**.

### What is required for a positive verdict

M1 must preserve declared commitment safety, match full validation where equivalence is claimed, reduce validation/optimization work materially, and improve executable actions under a compute deadline (or prove a meaningful complexity advantage) on nontrivial multi-vehicle dynamic instances — against B0 and B1.
