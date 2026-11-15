# Commitment viability and budgeted policy improvement

**Status:** Stage-2 formalization tied to implemented controllers (`BaselineAnchoredPredictiveCCE`, `DecisionFocusedBAP`).  
**Not claimed:** robustness to unmodeled uncertainty; hard-real-time preemption.

---

## 1. Objects (nominal plant)

| Symbol | Code object |
| --- | --- |
| Public observation \(o\) | `Observation` (+ `public_customer_count`) |
| Accepted obligations \(A\) | `observation.accepted` ∪ decision `newly_accepted` |
| Vehicle energy/time | `VehicleView.soc`, status, node, anchor |
| Noninterruptible action | first leg travel/charge/wait until next event |
| Certificate \(C\) | `CertificateStore.current` / `ContinuationCertificate` |
| Feasible continuation | `validate_continuation(public(o), routes, require_new=…)` OK |

**Inner viable set.** \((o,A)\in\mathcal{V}\) iff ∃ routes such that `validate_continuation` succeeds and covers \(A\).

---

## 2. Controller transition contract (what M1 alone does not state)

A **commitment-preserving anytime controller** satisfies, at every decide epoch:

1. **Incumbent first:** compute a feasible greedy-nominal decision \(\pi_0(o)\) under matched resources (`equivalence_mode` / matched `time_limit`).
2. **Independent verify:** every emitted decision (incumbent or override) is re-checked by `validate_continuation` before return (`_emit`).
3. **Anytime fallback:** if the cooperative wall budget is exhausted, emit the last verified incumbent (or empty UNKNOWN), never an unverified speculative plan.
4. **Store sync:** the shared `CertificateStore` is published for the **executed** decision; after override, `_sync_store_after_choice` republishes so the next `advance_or_invalidate` tracks the plant, not a discarded inner winner.

### Proposition A (certificate preservation under the contract)

**Assume:**
- (A1) Start with \((o_0,A_0)\in\mathcal{V}\) and a published certificate.
- (A2) Every `decide()` output that is applied to the plant was emitted only after independent `validate_continuation` success (or empty UNKNOWN with no new accepts).
- (A3) On override, the shared store is republished to the executed routes (Stage-1 repair).
- (A4) Between decisions, the plant evolves under the **same** nominal energy/travel/charge model used by the validator (including zero-duration arc handling).
- (A5) `advance_or_invalidate` either returns a truncated certificate still covering remaining accepted obligations, or invalidates (forcing re-certification before claiming CERTIFIED).

**Then:** for every previously accepted customer that has not completed or been rejected, after each allowed event-triggered decision there still exists a feasible continuation in \(\mathcal{V}\) covering that obligation—**or** the controller has explicitly fallen back to UNKNOWN / stripped new accepts and does not claim CERTIFIED coverage.

**Proof sketch (by induction on decide epochs).**  
Base: (A1).  
Inductive step: If the controller keeps the incumbent, the emitted routes are those just validated (A2) and already published by the inner CCE; viability holds. If it overrides, (A2)+(A3) ensure the executed routes are validated and become the certificate. Plant advance under (A4) either preserves the truncated suffix via `advance_or_invalidate` (A5) or invalidates, after which the next decide must re-enter \(\mathcal{V}\) before claiming CERTIFIED. Cooperative deadline paths emit the last verified incumbent (A2), never an unchecked speculative plan.

**Gap vs M1 alone:** M1’s store advance does not specify (i) anytime incumbent fallback under budget exhaustion, (ii) mandatory resync after a wrapper override, or (iii) matched-resource incumbent generation. Counterexample suite: `tests/test_commitment_viability_contract.py`.

### Explicit non-claims
- No guarantee if ALNS/wall-clock races emit different incumbents (`equivalence_mode` required for deterministic checks).
- No guarantee under stochastic energy (Spinelli-style) unless the validator uses the same distribution.
- No SPI guarantee on \(P^\star\) from \(\widehat{P}\)-scenario LCBs alone.

---

## 3. Budgeted policy improvement (forecast-conditional)

\[
\widehat{A}(o,a)=\widehat{\mathbb{E}}_{\widehat{P}}[R\mid o,a]-\widehat{\mathbb{E}}_{\widehat{P}}[R\mid o,\pi_0(o)].
\]

**Override rule (DecisionFocusedBAP):** screen by features → evaluate top-\(k\) with CRN scenarios → require
\(\widehat{A}(o,a) > \tau\) **and** confirmation-batch mean \(\ge \tau\) (prespecified \(\tau\), frozen before confirmatory eval).

**Assumptions for any confidence language:** i.i.d. scenarios under \(\widehat{P}\); finite action set with selection bias; cooperative interruption may truncate rollouts (fail-closed).

---

## 4. Gate result

Proposition A is the **operational contract** implemented and tested. It is stronger than “M1 validator returned OK once,” but it is **conditional and nominal**. It is **not** by itself a top-tier theory contribution without the empirical decision-advantage + EV mechanism results.
