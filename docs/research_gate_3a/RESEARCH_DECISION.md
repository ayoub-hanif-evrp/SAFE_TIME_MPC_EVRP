# Research decision — Gate 3A Multistage Commitment Viability

**Decision: NO-GO** for a Part 3 novelty claim based on multistage terminal viability.

Branch: `research/multistage-viability-gate`. Part 3 not started. Main / Part 1–2.5 artifacts unchanged in intent.

## Ten required questions

1. **Does a literature gap vs Han survive?**  
   **Partially.** Han does not already solve *dynamic causal routing forks* (Gate A). Gate B CEX-1 exhibits open-loop and fixed-route two-stage infeasible while feedback is feasible. The gap is real for **mechanism class**, not yet a paper.

2. **Does an exact nonanticipative feedback counterexample exist?**  
   **Yes.** `routing_fork_commitment` (CEX-1). Verified by oracle tests.

3. **Is adaptive charge alone enough for novelty?**  
   **No.** N2 `two_stage_charge_sufficient` shows Han-style two-stage matches feedback when only charge recourse is needed.

4. **Must residual budget be tracked?**  
   **Yes.** CEX-2: illegal \(\Gamma\) reset false-certifies feasibility.

5. **Is there a sound EVRP-specific theorem beyond Han / generic robust DP?**  
   **No.** Gate C Attempt C1 collapses to Bellman/labeling identical to the feedback oracle. Attempt C2 (rectangular envelopes) fails on CEX-1.

6. **Does a toy MPC use a real multistage horizon?**  
   **Yes.** `toy_mpc.run_feedback_mpc` re-solves exact multistage feasibility each step and applies one causal action. Matched baselines: open-loop, two-stage fixed-route, RH open-loop replan, oracle statuses, collapsed certificate.

7. **Is there a measurable trade-off vs the exact reference that supports a new certificate?**  
   **No.** The only sound “certificate” equals the exact reference (zero conservatism, zero savings).

8. **Are rectangular certificates / backups / solver preemption / skip-while-valid treated as novelty?**  
   **No.** Explicitly excluded per gate charter and Part 2.5 decision.

9. **Would publishing “multistage MPC with residual Γ and adaptive charge” be honest?**  
   **No** as a theoretical contribution. It is a correct engineering composition of known robust DP + commitments, not a new viability theorem.

10. **GO / REVISE / NO-GO?**  
    **NO-GO** for Part 3 under the Gate 3A novelty hypothesis. Optional **REVISE** path (not taken): drop theorem claims and reposition as an empirical systems paper with larger instances — out of scope for this gate’s GO criteria, which required a sound EVRP-specific result beyond Han/generic DP.

## What was established (keep)

- Exact independent multistage oracle with statuses `PROVEN_*`.
- Routing-fork gap vs open-loop and vs Han-style fixed-route two-stage.
- Residual-budget reset hazard.
- Negative controls preventing overclaim.
- Trustworthiness fixes on the research branch (stable seeds, worker customer boundary, horizon documented unused).

## What was falsified

Working hypothesis that a cheap terminal-viability certificate exists which is sound, beats policy-tree cost, and is not Han/generic DP — **falsified**.

## Next actions (not auto-started)

- Do **not** start Part 3 on this hypothesis.
- Leave `main` as the Part 1–2.5 line.
- If future work revises the question, open a new gate with a different principal target (e.g. empirical large-scale policy approximation with explicit non-novelty theory stance).
