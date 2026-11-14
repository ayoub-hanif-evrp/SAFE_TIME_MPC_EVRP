# Final certificate audit

## Accounting defect (fixed)

CertificateStore.publish previously stored observation.accepted only, omitting newly accepted customers from the same decide() call. Fixed via accepted= post-decision set.

## UNKNOWN / obligation gap

UNKNOWN with pending accepted customers is a failure condition of unconditional invariance; instrumented as obligation_gap and excluded from CERTIFIED claims.

## Regression audit (`A_low_soc_charge`, seed 7)

| Metric | Value |
|--------|------:|
| Certified verify failures | 0 |
| Publish accepted mismatches | 0 |
| UNKNOWN-with-accepted epochs | 0 |
| Replay ok | True |
| Accounting pass | True |

Gap sample: `[]`

## Corrected mathematical statement

**ConditionalCertificateValidity** (replaces withdrawn unconditional NominalCommitmentInvariance)

At any decision epoch where the controller emits status CERTIFIED_FEASIBLE for observation o and decision d, and an independent call to validate_continuation(o, d.routes, require_new=d.newly_accepted) returns ok under nominal physics, the published ContinuationCertificate's routes cover every customer in pending(o) ∪ d.newly_accepted, where pending(o) = accepted(o) \ (completed(o) ∪ in_service(o)). Coverage means each such customer is either already IN_SERVICE or appears as a future service visit in the certified suffixes. This is a per-epoch conditional validity proposition for certified claims — not an unconditional invariant across all epochs.

### Proof

- Definition. Let pending(o) and newly = d.newly_accepted. The controller's emit path sets status=CERTIFIED_FEASIBLE only after validate_continuation(..., require_new=newly) returns ok (independent verify before publish).
- By the semantics of validate_continuation (continuation_validate.py): pending obligations are pending(o); require_new adds newly; coverage is served_all ∪ in_service(o); missing = (pending(o) ∪ newly) \ covered must be empty for ok=True; duplicate service and illegal new accepts are rejected.
- Therefore, whenever the controller publishes a certificate under CERTIFIED_FEASIBLE, the independently verified routes cover pending(o) ∪ newly at that epoch.
- Publish records accepted := accepted(o) ∪ newly (post-decision set), so the certificate object's accepted field matches the obligations that were certified.
- QED (conditional on the certified-claim gate firing). This proof does not extend to epochs where status=UNKNOWN or the store is empty.

### Failure conditions

- CertificateStore.advance_or_invalidate may clear the certificate when accepted obligations appear dropped without completion/rejection, or when revalidation fails.
- decide() may return UNKNOWN with pending accepted customers when no scored feasible candidate exists and fallback revalidation fails — obligations may remain uncovered until a later epoch recovers or the episode records accepted-unfulfilled.
- Horizon-end residual probes may fail; accepted-unfulfilled is then honest plant state, not a certified continuation.
- Busy-vehicle / mid-action epochs can invalidate advanced suffixes relative to new anchors.

### Counterexample to the withdrawn claim

Concrete failure of the stronger (withdrawn) unconditional claim: on A_low_soc_charge seed 7 around t≈73.03 (arrive), CC-E-MPC emitted UNKNOWN while C4 and C5 remained accepted and store.current was absent — so preservation-at-every-epoch is false for the implemented controller. After accounting fixes, such epochs must be labeled obligation gaps, not CERTIFIED_FEASIBLE.

## Source-level comparison

See structured JSON in the closeout runner output / reproducibility package. M1 and CC-E-MPC share `CertificateStore`.

## Assessment preview

**INCREMENTAL_RESULT** — Technically sound after accounting fixes and a corrected conditional theorem, but CertificateStore persistence is largely inherited from M1 and/or lacks a compelling distinct empirical advance over M1 + stochastic MPC.
