# Commitment viability and budgeted policy improvement (Stage 2 draft)

**Status:** Draft formalization after Stage 1 repairs. Not yet a published theorem claim.

## 1. What M1 already gives

`CertificateStore` + `validate_continuation` already ensure: if a published certificate
advances without invalidation and the plant matches the nominal model, then the
truncated planned suffix remains a feasible continuation for currently accepted
obligations under the validator’s semantics.

**That alone is not a new contribution.**

## 2. Target statement (conditional, plant-nominal)

**Definition (inner viable set \(\mathcal{V}\)).** A public state \(o\) with accepted
set \(A\) is in \(\mathcal{V}\) if there exists a certificate \(C\) such that
`validate_continuation(public(o), C.routes, require_new=∅)` succeeds and covers \(A\).

**Proposition (certificate preservation under the controller’s transition rules).**  
Assume: (i) \(o_0\in\mathcal{V}\) with certificate \(C_0\); (ii) every emitted decision
passes independent `validate_continuation` before apply; (iii) the backup/incumbent
continuation is executable whenever speculative scoring is aborted; (iv) the plant
follows the nominal energy/travel/charge semantics used by the validator
(including instantaneous-arc handling as implemented).  
Then for every event-triggered step the controller is allowed to take, every
previously accepted customer remains coverable by some feasible continuation in
\(\mathcal{V}\) until completion or explicit rejection.

**Explicit non-claims:** no robustness to unmodeled travel/energy noise; no guarantee
under computation hard-preemption mid-solver; no guarantee if validation is skipped.

**What is new vs M1 (if proved carefully):** tying viability to **event-triggered
MPC transitions**, **anytime incumbent fallback**, and **override-resync of the
shared store** (Stage 1), not only “a certificate exists once.”

## 3. Budgeted policy improvement (forecast-model conditional)

Let \(\pi_0\) be the greedy-nominal incumbent. For alternative \(a\) and forecast
measure \(\widehat{P}\),

\[
\widehat{A}(o,a)=\widehat{\mathbb{E}}_{\widehat{P}}[R\mid o,a]-\widehat{\mathbb{E}}_{\widehat{P}}[R\mid o,\pi_0(o)].
\]

**Conditional SPI-style rule:** override only if \(\widehat{A}(o,a)>\tau\) after a
prespecified uncertainty adjustment (e.g., holdout confirmation scenarios / LCB),
with \(\tau\) frozen before confirmatory evaluation.

**Any probability statement must list:** i.i.d. scenario assumption under
\(\widehat{P}\); misspecification gap \(\widehat{P}\neq P^\star\); number of compared
actions (selection bias); confidence level; cooperative interruption of rollouts.

**This is not a guarantee on the unknown real environment.**

## 4. Gate

Proceed to Stage 3 only after: (a) the proposition is proved against the actual
simulator transition code paths; (b) a counterexample suite shows where M1 alone
is silent but the anytime+override contract matters.
