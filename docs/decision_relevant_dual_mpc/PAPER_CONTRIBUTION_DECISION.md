# Paper contribution decision

**Revision:** post-generic finite-state EVRP reference  
**Branch:** `research/decision-relevant-dual-mpc`

## Direct answer

We do **not** yet have a genuinely reusable, sound, **and computationally useful** dual-MPC pruning algorithm for dynamic EVRP.

We **do** have:

- Correct finite-state examples and a generic exact reference (restricted policy class).
- Sound bound-status handling (no silent discard).
- Causal model-inconsistency semantics.
- A proved family/generic resource upper-bound construction with adversarial checks.
- Established classical information-relaxation / nonanticipativity lessons.

We **do not** have a pruning method that reduces total decision computation enough to clear the research screening bar.

## Evidence (frozen suite)

From `computational_scaling.json` summary:

| Criterion | Result |
|-----------|--------|
| Generic prune retains exact first action | **8/8** |
| Heavy-ops strict improvement vs unpruned | **0/8** |
| Median wall-time reduction (generic prune) | **≈0.3%** |
| Screening target ≥20–30% median | **Failed** |

## Decision on the pruning hypothesis

**Retire further specialized toy-bound elaboration.**  
Retain the generic exact solver and frozen A/C/S reference bounds (DRUB/REUB/OTUB) as scientific artifacts.

Do **not** automatically pivot to another topic. Do **not** start Schneider / EVRP-TW-D / Amazon campaigns until a bound clears soundness **and** total-compute usefulness.

## Path forward (same algorithm family)

Only resume the pruning-as-contribution claim if a new general bound:

1. Remains valid (`VALID_BOUND ≥ Q*` on exact instances),
2. Shows zero false pruning,
3. Delivers meaningful total-runtime reduction on frozen nontrivial instances,
4. Has a structural edge beyond generic perfect-information relaxation,
5. Interfaces cleanly to FleetSimulator closed-loop checks.
