# Nominal commitment-certificate feasibility

## Certificate object

A `ContinuationCertificate` is a **persisted executable continuation**, not a metric:

- versioned fleet route suffixes
- served / planned service coverage
- per-vehicle anchors at publication
- accepted customer set
- assumptions tuple (`nominal_physics`, …)

## Theorem (NominalCommitmentInvariance)

**Claim.** Given an initially feasible certificate, exact nominal transition dynamics matching `FleetSimulator`, preservation of noninterruptible locked actions, and acceptance only when a complete feasible updated certificate exists (else execute a validated fallback), every accepted obligation retains a feasible completion plan at every subsequent decision epoch until completion, legal rejection, or episode termination with residual validation (or recorded accepted-unfulfilled when residual validation fails).

### Assumptions (explicit)

1. Nominal linear energy model  
2. Deterministic Euclidean travel and energy  
3. Independent chargers (no station capacity)  
4. Noninterruptible locked travel / service / charge  
5. Deadlines = customer window due dates  
6. Finite episode horizon / idle completion  
7. Accept only with a complete feasible updated certificate  
8. Public information only at decision epochs  

### Induction sketch

- **Base.** First accept publishes a `validate_continuation`-approved suffix covering pending ∪ newly accepted customers from current/post-action anchors.  
- **Event step.** Locked actions complete exactly; `advance_or_invalidate` strips realized visits; revalidation from new anchors succeeds or the certificate is cleared and coverage is not claimed.  
- **Decision step.** Execute only candidates that validate with `require_new`; otherwise execute the advanced fallback certificate, preserving already accepted obligations.  
- **Admission hygiene.** No resurrection of rejected customers; no re-admission of `in_service` customers; no second-vehicle dispatch to customers already in service.

### What is **not** claimed

- Robustness to energy/travel disturbances or forecast misspecification  
- Global multistage optimality of economic selection  
- That horizon-end residuals never fail (AU can still occur)  
- Novelty of expected-value rollout by itself  

**Supported by the plant:** yes (see `certificate_theory.theorem_document()`). No counterexample found under the stated assumptions; the statement is intentionally narrowed to **nominal** feasibility.
