# Proof attempts (Gate C)

## Target

One sound finite-horizon **terminal continuation** for accepted obligations under residual
uncertainty budget and adaptive charging, **cheaper than policy-tree enumeration**, and
not already Han labeling / generic robust DP.

## Attempt C1 — Robust Bellman / labeling certificate

**Statement (attempted).** The initial information state is terminally viable iff the
exact multistage feedback DP returns a winning policy.

**Implementation.** `terminal_viability_certificate` in
`src/safe_time_evrp/multistage/certificate.py` delegates to `feedback_feasible`.

**Soundness.** Immediate: the certificate is the exact feasibility oracle. On the discrete
model it never false-certifies.

**Conservatism vs oracle.** Zero gap (identical).

**Novelty verdict.** **Collapse.** This is the standard robust dynamic program / resource
extension labeling recursion under budgeted uncertainty. It is exactly the enumeration we
hoped to avoid. It is not an EVRP-specific closed-form bound, not cheaper than the oracle,
and not beyond Han-style labeling in spirit (Han labels on fixed routes; this labels on the
full action DAG).

**Stop condition hit.** Argument is only Bellman recursion / standard labeling → do not
claim a new theorem.

## Attempt C2 — Rectangular SOC/time envelope (abandoned)

**Idea.** Propagate worst-case SOC and time intervals with residual \(\Gamma\) as a scalar,
then require a charger-reachable return.

**Failure mode.** CEX-1 shows that **which** next node is admissible depends on the joint
`(time, SOC)` atom, not on interval bounds alone: the low world needs the direct arc; the
high world needs the detour. A rectangular envelope that unions both atoms either

- forbids both successors (too conservative / false infeasible), or
- allows a single open-loop choice that fails one world (unsound).

No short envelope rule recovered CEX-1 without reintroducing branching on observed atoms —
i.e. returning to the feedback DP.

## Conclusion for Gate C

No EVRP-specific terminal-viability theorem was established that is simultaneously sound,
strictly cheaper than exact multistage feedback, and beyond Han/generic robust DP.
Gate C outcome: **known-result collapse** (document only; no theorem claim).
