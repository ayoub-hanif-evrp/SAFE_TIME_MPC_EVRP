# Recursive feasibility for Commitment-Safe Stochastic MPC

**Status:** Conditional theorem under explicit plant assumptions.  
**Not claimed:** Unconditional safety; robustness to unmodeled travel/energy; hard real-time solvability.

Related withdrawn claim: unconditional NominalCommitmentInvariance (`docs/proofs/CERTIFICATE_FEASIBILITY_PROOF.md`).

---

## 1. System objects

At decision epoch \(t\) with public observation \(o_t\):

| Symbol | Meaning |
|---|---|
| \(x_t\) | Public plant state: vehicle nodes, SoC, loads, statuses, anchors, locked destinations |
| \(A_t\) | Accepted obligation set (irreversible) |
| \(U_t\) | Announced undecided requests |
| \(\mathcal{I}_t\) | Public information \(\sigma\)-algebra (no unreleased customer attributes) |
| \(u_t\) | First executable control (accept/reject subset of \(U_t\), first legs: travel/service/charge/wait) |
| \(C_t\) | Continuation certificate: routes covering \(A_t \cup A^{\mathrm{new}}_t\) under nominal physics |
| \(\pi^{\mathrm{b}}\) | Backup policy: advance/revalidate \(C_t\); if invalid, refuse new accepts and emit last independently verified continuation or empty UNKNOWN |

**Feasible commitment set**

\[
\mathcal{V}_t := \bigl\{(x_t,A_t):\exists\,C\text{ s.t. }\mathrm{Validate}(x_t,A_t,C)=\mathrm{true}\bigr\}.
\]

In code: `validate_continuation(public_snapshot(o_t), routes, require_new=newly_accepted)`.

---

## 2. MPC law (abstract)

At each event-triggered epoch \(t\in\mathcal{T}\):

1. Observe \(o_t\) measurable w.r.t. \(\mathcal{I}_t\).
2. Advance certificate; if still valid, retain as incumbent \(u^{\mathrm{inc}}_t\).
3. Sample finite-demand scenarios \(\{\xi^{(s)}\}_{s=1}^S\) measurable w.r.t. \(\mathcal{I}_t\) (nonanticipative).
4. Solve (approximately) the finite-horizon problem in `docs/methodology/COMMITMENT_SAFE_STOCHASTIC_MPC.md` subject to:
   - hard coverage of \(A_t \cup A^{\mathrm{new}}_t\) at stage 0,
   - terminal constraint \((x_{t+H}^{(s)}, A_{t+H}^{(s)}) \in \mathcal{X}_f\) for every scenario (or certified backup suffix),
   - locked noninterruptible actions unchanged until their anchors.
5. Apply **only** the stage-0 action \(u_t^\star\); discard open-loop tails.
6. If the solver fails or the cooperative budget expires without a verified \(u_t^\star\), apply \(\pi^{\mathrm{b}}(o_t)\).

---

## 3. Terminal feasible set

Define the **nominal terminal set**

\[
\mathcal{X}_f := \bigl\{(x,A):\exists\,C_f\text{ covering }A\text{ from }x\text{ under nominal energy/travel/charge, respecting time windows and noninterruptible locks}\bigr\}.
\]

**Backup-policy condition.** \(\pi^{\mathrm{b}}\) is **admissible** if whenever \((x_t,A_t)\in\mathcal{V}_t\) and no new accepts are forced, \(\pi^{\mathrm{b}}\) returns a control whose independent validation succeeds or explicitly signals UNKNOWN without adding obligations.

---

## 4. Assumptions

| Id | Assumption |
|---|---|
| (N1) | Nominal deterministic energy = Schneider linear arc energy; travel times deterministic Euclidean / instance arcs. |
| (N2) | Plant, validator, and replay use the **same** energy and timing model (including zero-duration arcs). |
| (N3) | Between decision epochs, the plant applies the issued first action until the next event; locked actions are noninterruptible. |
| (N4) | New accepts are issued only when a validated certificate covers \(A_t \cup A^{\mathrm{new}}_t\). |
| (N5) | On timeout / solver failure, \(\pi^{\mathrm{b}}\) is admissible (N4 holds with \(A^{\mathrm{new}}=\emptyset\) if needed). |
| (N6) | Terminal constraint: every candidate open-loop plan either ends in \(\mathcal{X}_f\) under nominal physics for the residual accepted set, or attaches a pre-validated certified suffix \(C_f\). |
| (N7) | No unmodeled disturbances: realized travel/energy match the nominal model used in Validate. |

**Explicitly excluded:** stochastic energy without robust constraints; adversarial travel; claims from scenario sampling alone.

---

## 5. Theorem (conditional recursive commitment feasibility)

**Theorem (RF-CS-SMPC).**  
Assume (N1)–(N7). Suppose \((x_{t_0},A_{t_0})\in\mathcal{V}_{t_0}\) with a published certificate. Let the closed loop apply the MPC law of §2 at every subsequent decision epoch.

Then for every decision epoch \(t\ge t_0\):

1. \(A_t\) only grows by validated new accepts (or stays unchanged under backup);
2. either \((x_t,A_t)\in\mathcal{V}_t\), or the controller emits UNKNOWN / strips new accepts and **does not** claim `CERTIFIED_FEASIBLE`;
3. every customer in \(A_t\) that is not yet completed remains covered by some nominal continuation at every certified epoch.

**This is recursive feasibility of the commitment set under the nominal model**, not almost-sure service under demand uncertainty.

---

## 6. Proof

**Base case.** At \(t_0\), \((x_{t_0},A_{t_0})\in\mathcal{V}_{t_0}\) by hypothesis.

**Inductive hypothesis.** At epoch \(t\), either \((x_t,A_t)\in\mathcal{V}_t\) with certificate \(C_t\), or the controller is in an explicitly non-certified state with no unverified new accepts (by (N4)–(N5)).

**Inductive step.** Consider the next decision epoch \(t^+\).

**Case A — MPC returns a verified optimizer output.**  
By construction of the stage-0 constraint and independent `Validate`, \(A_{t^+}=A_t\cup A^{\mathrm{new}}\) is covered at emit time. (N3)–(N2) imply the plant’s first-action evolution matches the certificate prefix. At \(t^+\), `advance_or_invalidate` either:

- returns a truncated certificate still covering residual obligations (still in \(\mathcal{V}_{t^+}\)), or
- invalidates, forcing re-entry via a new solve or \(\pi^{\mathrm{b}}\).

If the stochastic plan satisfies (N6), residual obligations beyond the prediction horizon remain in \(\mathcal{X}_f\) under nominal physics, so horizon truncation cannot silently drop them at certified emits.

**Case B — Timeout / failure.**  
(N5) applies \(\pi^{\mathrm{b}}\). No unverified accepts are added. If a previous certificate still validates after advance, \(\mathcal{V}\) is preserved; otherwise the controller must not claim certification (part 2 of the theorem).

**Case C — Realization of new announcements.**  
New requests enter \(U_{t^+}\) but not \(A_{t^+}\) until accepted. Rejecting them preserves \(\mathcal{V}\). Accepting them requires (N4).

**Conclusion.** By induction, parts (1)–(3) hold for all decision epochs. □

---

## 7. What the theorem does *not* say

- It does **not** say a route validated at time \(t\) remains valid without revalidation after events — advance may invalidate; the theorem tracks re-entry into \(\mathcal{V}\).
- It does **not** guarantee feasibility under energy/travel misspecification. If (N7) fails, replace (N1)/(N7) by a robust constraint set before claiming RF.
- Scenario demand uncertainty affects the **objective**, not the hard commitment invariant under (N1)–(N7).
- Approximate solvers preserve RF **only** through the independent validation gate and backup policy, not because ALNS is exact.

---

## 8. Code anchors

| Concept | Implementation target |
|---|---|
| \(\mathcal{V}_t\) | `continuation_validate.validate_continuation` |
| Certificate advance | `CertificateStore.advance_or_invalidate` |
| Public info | `public_snapshot.make_public_snapshot` |
| Backup | Incumbent certificate / last verified routes in `CommitmentSafeStochasticMpc` |
| Terminal suffix | Certified residual routes required before accept; see methodology doc |
| Tests | `tests/test_commitment_safe_stochastic_mpc.py` |

---

## 9. Relation to prior Stage-2 note

`COMMITMENT_VIABILITY_AND_POLICY_IMPROVEMENT.md` formalizes wrapper contracts (BAP/DF-BAP). This document supersedes that **research direction** for the paper: the invariant is attached to the **MPC law**, not to baseline-anchored overrides.
