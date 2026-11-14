# Corrected certificate proposition

## Withdrawn claim

**NominalCommitmentInvariance** (unconditional preservation of a feasible plan at every decision epoch) is **withdrawn**. It is incompatible with implemented behavior: certificates can invalidate, and `decide()` can emit `UNKNOWN` while accepted customers remain pending (documented historically around t≈73 on `A_low_soc_charge` seed 7).

## Proposition: ConditionalCertificateValidity

At any decision epoch where the controller emits `CERTIFIED_FEASIBLE` for observation \(o\) and decision \(d\), and an independent `validate_continuation(o, d.\mathrm{routes}, \mathrm{require\_new}=d.\mathrm{newly\_accepted})` returns ok under nominal physics, the published certificate’s routes cover every customer in \(\mathrm{pending}(o)\cup d.\mathrm{newly\_accepted}\).

### Assumptions

Nominal linear energy; deterministic Euclidean travel/energy; independent chargers; noninterruptible locked actions; deadlines = window due dates; finite horizon; public information only; soundness of `validate_continuation` for nominal suffixes.

### Proof

1. The emit path sets `CERTIFIED_FEASIBLE` only after independent `validate_continuation(..., require_new=newly)` succeeds.  
2. By validator semantics, obligations are `pending(o) ∪ newly`, and ok implies this set is ⊆ `served ∪ in_service(o)`.  
3. Publish records `accepted := accepted(o) ∪ newly`.  
4. Therefore every certified publish covers the post-decision obligation set at that epoch.  

This does **not** extend to `UNKNOWN` epochs or empty stores.

### Failure conditions

Advance/invalidate clearing the store; scored-candidate exhaustion with failed fallback; horizon residual failure → accepted-unfulfilled; busy-anchor mismatch.

### Distinctions

| Outcome | Meaning |
|---------|---------|
| CERTIFIED_FEASIBLE | Independent nominal coverage now |
| UNKNOWN + obligation_gap | Accepted customers currently uncovered by the emitted plan |
| accepted_unfulfilled | Plant terminal: accepted without residual-feasible completion |
| Simulator natural end | May still leave residual-feasible pending (not AU) |

Machine-readable statement: `certificate_theory.theorem_document()`.
