# Recursive feasibility / certified-emission soundness

**Status:** Weakened to a claim the implementation actually supports.  
**Closed-loop evidence:** `CERTIFIED_FEASIBILITY_LOST` occurs (e.g. CSS-MPC on `c106C15`, `r103C10`, `r105C15`). A theorem asserting unconditional forward invariance of \(\mathcal{V}\) is **false** for the current plant+controller pair.

Closed-loop certificate-loss events are reported in paper evaluation profiles
(`docs/experiments/MPC_PAPER_EVAL_RESULTS.json`).

---

## 1. What is *not* claimed

We **withdraw** any statement of the form:

> Starting from \((x,A)\in\mathcal{V}\), every closed-loop transition under the MPC law remains in \(\mathcal{V}\).

Observed counterexamples: status `CERTIFIED_FEASIBILITY_LOST` with outstanding accepted customers and empty/unvalidated fallback routes. Causes include travel-timing Validate failures, charge-duration replay mismatch, and cooperative-budget exhaustion — not a single bookkeeping defect.

A theorem that allows feasibility loss and then restricts attention to epochs that remain certified is **not** a recursive-feasibility theorem.

---

## 2. Verified properties

### 2.1 Certified-emission soundness

**Definition.** An emission is **certified** if status = `CERTIFIED_FEASIBLE`.

**Theorem (Certified-emission soundness).**  
Assume nominal energy/travel (N1)–(N2) and independent `validate_continuation`. Whenever `CommitmentSafeStochasticMpc` returns status `CERTIFIED_FEASIBLE`:

1. `_try_commit` succeeded: independent Validate covers \(A_t \cup A^{\mathrm{new}}\) for the emitted routes;
2. the certificate store was published for **exactly** those routes and post-decision accepts;
3. `newly_accepted` is empty unless Validate covered those customers;
4. no speculative accepts appear in the Decision after a failed Validate.

**Proof.** Immediate from transactional `_try_commit` / `_emit_fallback` (Gate 1 tests). □

This is **epoch-wise soundness of certified claims**, not recursive feasibility of the viable set.

### 2.2 Scenario-terminal honesty

**Proposition.** A candidate is labeled `STOCHASTIC_TERMINAL` only after
`verify_terminal_commitment` succeeds on the **declared** scenario set. Cache keys are
`(FirstActionKey, scenario_set_signature)`. Empty-future success is not reused for
nonempty scenarios. Scenario-failed candidates are excluded from the stochastic
selection pool; unchecked candidates may enter only an explicit nominal-backup pool
with a weaker declared guarantee.

**Proof.** Direct from `_terminal_filter` cache keying and selection policy tests in
`tests/test_scenario_terminal_validity.py`. □

---

## 3. Conditional certificate advancement (partial RF fragment)

**Proposition (Advance under matching nominal dynamics).**  
If a certificate \(C\) covers \(A\) at epoch \(t\), the plant applies the certified first action, and between \(t\) and \(t^+\) the plant evolves under the **same** nominal model used by Validate with no unmodeled disturbance, then `advance_or_invalidate` either:

- returns a truncated certificate covering residual \(A\setminus\mathrm{completed}\), or
- invalidates (forcing re-certification before a new certified claim).

**Proof sketch.** Truncation removes completed/in-service prefix visits; residual Validate semantics match M1 store advancement under (N1)–(N3). □

**Gap:** Invalidation + failed re-solve + failed backup ⇒ `CERTIFIED_FEASIBILITY_LOST`. The controller **reports** loss; it does not preserve \(\mathcal{V}\).

Inductive certificate-shifting / terminal-backup arguments are **not** used here as a full RF proof, because interruption, charge-duration discreteness, and cooperative deadlines leave uncovered transitions in the closed loop.

---

## 4. Terminal commitment role

Horizon-end `verify_terminal_commitment` after `freeze_simulator_at_horizon` strengthens **candidate filtering** (reject plans whose projected terminal state has no backup). It does **not** by itself restore recursive feasibility once a certificate is lost online.

---

## 5. Guarantee taxonomy

| Claim | Status |
|---|---|
| Certified-emission soundness | **Supported** |
| Conditional advance-or-invalidate | **Supported** under nominal matching dynamics |
| Forward invariance of \(\mathcal{V}\) for all closed-loop transitions | **Withdrawn** |
| Robust RF under energy noise | **Not claimed** |
| Stochastic RF from scenario sampling | **Not claimed** |

---

## 6. Code anchors

| Concept | Code |
|---|---|
| Transactional commit | `CommitmentSafeStochasticMpc._try_commit` |
| Loss status | `STATUS_LOST = CERTIFIED_FEASIBILITY_LOST` |
| Horizon freeze | `freeze_simulator_at_horizon` |
| Terminal verify | `verify_terminal_commitment` |
| Loss events in eval | `docs/experiments/MPC_PAPER_EVAL_RESULTS.json` (`loss_events`) |
