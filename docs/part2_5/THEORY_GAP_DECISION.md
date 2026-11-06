# Theory gap decision (Part 2.5)

## Question investigated

Can a computation-aware MPC controller maintain a provably admissible EVRP continuation across noninterruptible actions, asynchronous optimization, bounded energy/time uncertainty and irrevocable commitments, with less conservatism or computation than strong standard alternatives?

## Literature (no novelty from combination alone)

- Robust EVRP / adaptive robust energy: Jeong et al. (2024); Han et al. (2025, abstract).
- Resource-extension / labeling: Desaulniers et al. (2016, abstract); EVRP literature.
- Anytime routing with prompt confirmation: Sivagnanam et al. (2026) — not electric.
- Computation-constrained event-triggered MPC: Gräfe and Trimpe (2025).

Combining a rectangle check, a backup, a deadline and a trigger is not itself a new theorem.

## Exact closed-loop counterexamples (qualitative)

| Situation | Outcome |
| --- | --- |
| Physical event during optimization | Candidate is stale; must not apply; backup may still be valid after the event (engineering rule + Prop. 2 if hypotheses hold). |
| Accepted customer + outdated first action | New acceptance requires a new certificate; an old action identity cannot commit. |
| Valid backup, interrupted solve | Timeout keeps the backup if it still certifies; tested. |
| Backup expires before solver returns | If the intervening event changes the action identity or commitments, the backup must be re-checked; if it fails, report infeasibility. |
| Fixed-target charge depends on realized SOC | Counterexample P: upper corner is insufficient; theorem narrowed. |
| New customer whose insertion breaks obligations | Certificate rejects; acceptance is not finalized without a feasible required set. |

## Weakest assumptions for a meaningful closed-loop theorem

Full recharge, rectangular independent bounds, fixed sequences between decisions, noninterruptible actions whose end anchors are predicted, rejection allowed for new requests, and a deadline that only protects the backup rather than guaranteeing a new optimum. Under those assumptions, the proved statements remain Propositions 1 (narrowed), 2, 3 and 5 from Part 2: exact full-charge rectangle, one-arc shift, rejection, and “no safety need to re-solve while hypotheses hold.”

That is **not** a theorem that asynchronous optimization plus acceptance plus preemption yields less conservatism than every-event robust MPC with the same certificate.

## Decision

**No nontrivial new MPC theorem with a demonstrated algorithmic advantage was identified.**

The repository is verified research infrastructure: an exact (narrowed) certificate, a hard deadline supervisor, a disturbed plant with replay, and matched baselines. Implementation invariants are labeled as such.

Closest honest paper framing: a systems / reproducible-control paper on deadline-aware certified routing MPC, not a claim of a new feasibility theorem beyond monotone full-charge resource propagation.
