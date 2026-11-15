# Recursive feasibility for Commitment-Safe Stochastic MPC

**Status:** Conditional theorem with algorithm–theorem correspondence in code.  
**Not claimed:** Unconditional safety; robustness to unmodeled travel/energy; hard real-time; stochastic-energy RF.

Related withdrawn claim: unconditional NominalCommitmentInvariance (`CERTIFICATE_FEASIBILITY_PROOF.md`).

---

## 1. Objects

| Symbol | Meaning | Code |
|---|---|---|
| \(x_t, A_t\) | Public state and accepted obligations | `Observation` |
| \(\mathcal{V}\) | Feasible commitment set | \(\exists C:\mathrm{Validate}(x,A,C)\) |
| \(u_t\) | First-stage control | `Decision` (routes, newly, rejects) |
| \(C_t\) | Certificate | `CertificateStore` |
| \(\pi^{\mathrm{b}}\) | Backup | warm-started certified routes, **no new accepts** |
| \(\mathcal{X}_f\) | Terminal set | `verify_terminal_commitment` |

\[
\mathcal{V}:=\bigl\{(x,A):\exists\,C\;\mathrm{Validate}(x,A,C)=\mathrm{true}\bigr\}.
\]

---

## 2. Admissible emission rule (implemented)

A controller output is **admissible** only if one of the following holds:

**(E1) Certified commit.** Independent `Validate` succeeds for \(A_t\cup A^{\mathrm{new}}\), terminal commitment holds on every scored scenario, then the store is published and `newly_accepted = A^{\mathrm{new}}`. Status = `CERTIFIED_FEASIBLE`.

**(E2) Certified backup.** Speculative winner is discarded; `newly_accepted = []`; a previously verified (or revalidated) continuation covering **existing** \(A_t\) is committed. Status = `CERTIFIED_FEASIBLE`.

**(E3) Feasibility loss (assumption failure signal).** No validated continuation for existing \(A_t\) exists. Status = `CERTIFIED_FEASIBILITY_LOST`. Decision still lists existing accepts (never silently drops them) but **claims no certificate** and adds **no** new accepts.

**(E4) Vacuous UNKNOWN.** Only when \(A_t=\emptyset\) and no certified plan is available. Not used to “paper over” uncovered existing obligations.

**Transactional emit (Gate 1):** store mutation and `newly_accepted` occur only inside successful (E1)/(E2). Failed validation never returns speculative accepts.

---

## 3. Assumptions

| Id | Assumption |
|---|---|
| (N1) | Nominal Schneider linear energy; deterministic travel times. |
| (N2) | Plant, optimizer, validator, replay share the same energy/timing model (arc rebuild when consumption changes). |
| (N3) | Locked noninterruptible actions execute to their anchors; first-action only between events. |
| (N4) | New accepts issued only via (E1). |
| (N5) | On timeout / empty scored set, emission is (E2) if possible, else (E3)/(E4). |
| (N6) | Every certified candidate satisfies stage-0 Validate **and** horizon-end \(\mathcal{X}_f\) via `project_to_horizon` + `verify_terminal_commitment`. |
| (N7) | Realized plant transitions match the nominal model used in Validate (no unmodeled disturbances). |
| (N8) | Certificate `advance_or_invalidate` under (N3)+(N7) either returns a truncated certificate still covering residual \(A\), or invalidates — in which case (E2) re-enters \(\mathcal{V}\) before claiming certified, or (E3) signals loss. |

**Excluded:** stochastic energy RF; scenario sampling as a robust guarantee.

---

## 4. Theorem (RF-CS-SMPC, strengthened)

**Theorem.** Assume (N1)–(N8). Suppose \((x_{t_0},A_{t_0})\in\mathcal{V}\) with a published certificate. Let the closed loop apply `CommitmentSafeStochasticMpc` with the admissible emission rule at every event-triggered epoch.

Then for every decision epoch \(t\ge t_0\) **at which the status is `CERTIFIED_FEASIBLE`**:

1. \((x_t,A_t)\in\mathcal{V}\) with a published certificate matching the emitted routes;
2. \(A_t\) grew from \(A_{t_0}\) only by (E1) accepts;
3. after the plant applies the emitted first action and evolves under (N3)+(N7) to the next decision epoch \(t^+\), either advance yields \((x_{t^+},A_{t^+})\in\mathcal{V}\), or the next admissible emission restores \(\mathcal{V}\) via (E1)/(E2) before claiming certified.

**Equivalently:** under (N1)–(N8), the set of certified viable states is **forward invariant** for the closed loop. The status `CERTIFIED_FEASIBILITY_LOST` is **not** an RF-preserving mode — it flags that some assumption failed (typically (N7)/(N8)); the algorithm refuses to pretend otherwise.

---

## 5. Proof sketch (transition model)

**Base.** \((x_{t_0},A_{t_0})\in\mathcal{V}\) by hypothesis.

**Inductive step (certified epoch \(t\)).** Emission is (E1) or (E2).

- **(E1):** Transactional `_try_commit` publishes only after Validate. Terminal filter enforces (N6). First-action execution under (N3) follows the certified prefix. At \(t^+\), (N8) either advances the certificate (still in \(\mathcal{V}\)) or invalidates; the next decide must use (E1)/(E2) to reclaim \(\mathcal{V}\) before certified status.
- **(E2):** No new accepts; Validate covers existing \(A_t\); same advance argument.

**Loss path.** If Validate fails for all backups, emission is (E3). Theorem’s invariance claim applies only to certified epochs; (E3) is the explicit witness that (N1)–(N8) did not hold for that transition.

**New announcements.** Enter \(U_t\) only; join \(A_t\) solely through (E1).

□

---

## 6. Algorithm–theorem correspondence tests

| Claim | Test |
|---|---|
| No speculative accepts on failed commit | `test_gate1_invalid_candidate_cannot_introduce_accepts` |
| Store records only emitted certified action | `test_gate1_failed_commit_does_not_publish_and_strips_new_accepts` |
| Existing obligations not silently dropped | `test_gate1_loss_reported_when_existing_uncovered` |
| Terminal ≠ stage-0 | `test_gate2_*` |
| Certified ⇒ published | `test_gate3_rf_emission_never_adds_accept_without_certificate` |
| Loss status on uncovered \(A_t\) | `test_gate3_assumption_counterexample_loss_status` |

---

## 7. Guarantee taxonomy

| Guarantee | Status |
|---|---|
| Nominal recursive commitment feasibility under (N1)–(N8) | **Claimed** (this theorem) |
| Robust RF under energy uncertainty | **Not claimed** |
| Almost-sure RF under demand scenarios alone | **Not claimed** (scenarios affect objective + terminal checks, not robust sets) |
| Hard real-time interruptibility | **Not claimed** (cooperative wall + (E2)/(E3)) |
