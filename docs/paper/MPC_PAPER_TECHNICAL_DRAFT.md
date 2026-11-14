# Certificate-Carrying Economic MPC for Dynamic EV Routing with Irreversible Commitments

**Technical draft (development evidence only — holdout frozen)**  
**Internal assessment: `CERTIFICATE_ONLY`**

## Abstract

We study dynamic electric vehicle routing with time windows, battery constraints, and *irreversible* customer acceptances. We formulate Certificate-Carrying Economic Model Predictive Control (CC-E-MPC): a persistent executable commitment certificate is a hard feasibility invariant under nominal physics, while forecast-based expected economic value ranks certificate-feasible first actions. A restricted charging oracle shows that removing worst-scenario regret floors restores proactive charging. Matched development experiments find mixed service gains versus reactive B1 and substantial overlap with ordinary stochastic MPC. We therefore center the scientific claim on the certificate mechanism and its nominal invariance theorem, not on a blanket superiority claim for expected-value lookahead.

## 1. Problem

Fleet of EVs; Euclidean travel; nominal linear energy; customer windows; depot and chargers. Requests appear over time. Acceptance is irrevocable: the controller must retain a feasible completion plan for every accepted obligation under stated physical assumptions. Noninterruptible travel, service, and charging actions constrain replan timing.

## 2. Algorithm (CC-E-MPC)

### 2.1 Certificate

A continuation certificate stores versioned route suffixes, anchors, accepted set, and coverage. It is advanced through physical events and revalidated, or invalidated.

### 2.2 Pseudocode

```
initialize empty CertificateStore
at each decision event on observation o:
  C ← advance_or_invalidate(store, o); revalidate C or clear
  A ← generate_first_actions(o)           # serve/accept/reject/charge/wait/ALNS
  F ← { a ∈ A | Validate(o, a) = CERTIFIED_FEASIBLE }
  if F = ∅:
      execute fallback(C) if valid else idle; return
  for a in F:
      J(a) ← E_ω[ CausalRollout(a, ω; B1-recourse) ]   # fail-closed if replay invalid
  a* ← argmax_{a∈F} J(a)                 # NO min_Δ≥0 vs B1
  execute first physical action of a*
  publish Validate(o, a*) as new certificate
```

### 2.3 Hard vs soft

- Hard: `Validate` for existing + newly accepted commitments.  
- Soft: expected service/−AU/−distance.  
- Not hard: beating B1 in every scenario.

## 3. Theorem and assumptions

See `docs/proofs/CERTIFICATE_FEASIBILITY_PROOF.md`.

**NominalCommitmentInvariance** (induction over epochs): under exact nominal dynamics, noninterruptible action preservation, and accept-only-with-certificate, accepted obligations retain a feasible completion plan at decision epochs.

**Not claimed:** disturbance robustness, forecast-misspecification guarantees, multistage optimality.

## 4. Baselines

| Baseline | Description |
|----------|-------------|
| B1 | Full-validation reactive ALNS–MPC |
| M1 | Certificate-carrying ALNS (no forecast EV ranking) |
| Stochastic MPC | Counterfactual EV argmax, weak persistence |
| CC-E-MPC | This paper’s controller |
| Ablations | No forecast; no persistent certificate |

ALNS is an internal route engine, not the contribution.

## 5. Experimental protocol

- Development cases from the accelerated matrix; Phase 3E seeds `{3,7,11}` then a priori expansion `{13,17,19}`.  
- Matched releases and forecast seeds.  
- Independent replay gates superiority claims.  
- Holdout unevaluated until implementation freeze.  
- Objective weights not tuned on wins.

### Oracle

Case-A restricted set `{serve, charge}`: serve ≈88, charge ≈122.29. Live `decide()` selects charge; episode replay-valid. Unrestricted EV may prefer wait; reported honestly.

## 6. Findings (truthful)

1. Risk-floor switching blocked beneficial charge; EV among feasible actions restores it on the restricted oracle.  
2. Certificate regressions pass for announcement / travel / service / low-SOC / timeout / illegal admission.  
3. Core grid: 2 wins / 1 loss vs B1; 6/9 outcomes identical to stochastic MPC.  
4. Expansion mean completed Δ vs B1 is negative (−0.22): gains are not robust.  
5. Assessment: **`CERTIFICATE_ONLY`**.

## 7. Novelty relative to published lines of work

We do **not** claim novelty for expected-value stochastic rollout, safety filters, backup plans, or ALNS alone. Related themes include proactive charging / stochastic lookahead in dynamic EVRP and prompt commitments with non-myopic routing.  

Our candidate distinction is **persistent executable certificates** under event-driven noninterruptible EV operations with a nominal invariance argument. Because closed-loop outcomes often match stochastic MPC with the same candidates/forecasts, we do **not** market CC-E-MPC as a new dominance result over standard lookahead. If reviewers treat the certificate+theorem as incremental relative to M1-style retention, that critique is acknowledged.

## 8. Limitations

- Nominal (not robust) feasibility.  
- Small development grids; holdout untouched.  
- Wait can outscore charge under unrestricted EV.  
- Thin / mixed predictive gains.  
- Forecast quality not stress-tested for misspecification.

## 9. Conclusion

CC-E-MPC corrects the conceptual error of treating scenario-wise regret vs B1 as safety. The durable object for a manuscript under current evidence is the **commitment certificate**: its representation, advancement, hard admission rule, and nominal invariance. Predictive economic selection is the surrounding control law; it is necessary for the charging oracle but not yet a demonstrated top-tier empirical superiority story.
