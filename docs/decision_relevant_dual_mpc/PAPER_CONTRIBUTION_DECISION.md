# Paper contribution decision

**Revision:** urgent correctness repair (post-`b3c709f` audit)  
**Branch:** `research/decision-relevant-dual-mpc`  
**Record:** `URGENT_CORRECTNESS_REPAIR.md`

## Direct answer

We do **not** yet have a top-tier methodological contribution: a sound, nontrivial, computationally useful dual-MPC / information-aware search method for dynamic EVRP.

We **do** have an in-progress correction that:

- Quarantines an invalid general TEI bound (counterexample: 9.85 vs feasible 14.625).
- Separates restricted vs full finite-state oracle claims.
- Restores fleet-level acceptance and full release lifecycle.
- Starts a belief-state event reference and a discriminating development suite.

We **do not** have a repaired tight general bound, nor evidence that any bound reduces total decision computation on nontrivial instances.

## Evidence retained (do not rewrite)

Frozen 8-instance screen under the pre-repair generic TEI:

| Criterion | Result |
|-----------|--------|
| Generic prune retains exact first action | **8/8** (behaviorally degenerate: same action/value) |
| Heavy-ops strict improvement vs unpruned | **0/8** |
| Median wall-time reduction (generic prune) | **≈0.3%** |
| Screening target ≥20–30% median | **Failed** |

That negative compute result stands. The new finding is stronger: those eight runs were not a valid dynamic multi-request problem in the first place.

## Decision

1. **Fix the existing project** — same branch; no new research gate; no Schneider / EVRP-TW-D / Amazon pivot.
2. **Correctness before pruning claims** — model, oracle scope, and bound must match.
3. **Possible future contribution** (not assumed): anytime / deadline-sensitive policy-tree search that uses EVRP time–energy reachability and causal information partitions to produce feasible incumbents under a compute deadline — only if it improves a real computation–service–reliability frontier vs exact search, information relaxations, and strong stochastic MPC baselines.

## Path forward

Only resume “pruning / information-aware search as contribution” if:

1. Oracle statuses match a declared finite action class and pass multi-customer / multi-EV / charge / announcement tests,
2. Any `VALID_BOUND` satisfies \(Q_{\mathrm{upper}}\ge Q^\star\) on adversarial cases,
3. Discriminating instances show distinct causal decisions,
4. Total-runtime reduction clears the screening bar without losing decision quality.
