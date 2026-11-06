# Part 2 research decision

## Verdict

**The repository now has a correct, tested specialization of known monotone route checking and known backup MPC. It does not have a new control theorem that would justify a top-tier theory paper, and it does not justify a large Part 3 campaign as confirmation of a new principle.**

Part 3 should not start on the strength of this result.

## What was proved

Proposition 1: on the linear Schneider plant, with a fixed sequence and an independent rectangle, robust feasibility is exactly the upper-corner simulation.

Proposition 2: a realization inside the rectangle preserves the suffix.

Proposition 3: rejecting an announced customer preserves the certificate. Accepting one requires a new certificate.

Proposition 4: an idle delay no longer than a clock that was already used in the certificate preserves it. The code re-checks rather than trusting the inequality alone.

Proposition 5: while those hypotheses hold, another optimization is not required for safety.

The proofs are in `FEASIBILITY_PROOFS.md`, `COMPUTATION_AWARE_MPC.md`, and `TRIGGERING_THEORY.md`. They use monotonicity of this plant. They are the standard resource argument, written for this commitment and timing model so the controller cannot claim more than it has.

## What was built and tested

- A certificate that can return feasible, infeasible, or unknown, with the infeasible label reserved for a proved corner or a missing commitment.
- A backup that a stale or failed candidate cannot overwrite.
- A process supervisor that kills a late worker. Timeout, crash, and exception are separate results.
- Four triggers, of which only the validity-aware rule has a proof, and that proof says safety does not need the extra solves.
- Baselines B0 (nominal one-customer insertion), B1 (Part 1 MPC), B2 (fixed-period robust), B3 (every-event robust), B4 (the same anytime insertion, which B3 already is), and B5 (validity-aware).
- Cases A–H as unit tests, plus the original Part 1 suite.

The development pilot is one deterministic easy toy. Its manifest refuses a second overwrite. It is not a statistical comparison and not a holdout.

## What is not new

- Upper-corner resource propagation for a fixed electric route (labeling algorithms; Han et al. 2025 at abstract level; Jeong et al. 2024 for adaptive robust EVRP).
- A feasible incumbent used when the search fails.
- Anytime improvement under a time limit (Sivagnanam et al. 2026, without batteries).
- Event-triggered robust MPC under a computation limit (Gräfe and Trimpe 2025, for nonlinear systems that are not routes).
- Self-triggered MPC for plants with a bounded disturbance tube.

The prefix cache was measured only as a correctness check. It is not advertised as an algorithm.

## Why the three target contributions fail

**Contribution A, a new EVRP certificate.** The exact rectangle test is necessary and sufficient here, so there is no conservatism to remove inside the supported model. The inflated test is more conservative, which is the wrong direction. On a non-monotone plant the code correctly refuses to certify. That refusal is not a new test.

**Contribution B, a computation-aware feasibility theorem.** Proposition 4 is real and small. It does not cover a vehicle that is already on an arc, a killed solve, and a new acceptance in one statement. The program's stale-result rule is necessary and was tested. It is an invariant, not the theorem that was hoped for. Gräfe and Trimpe and the predictive-triggered MPC line already treat nonzero solve time for other plants.

**Contribution C, a principled trigger.** Proposition 5 is the honest one: if the backup is valid, do not re-solve for safety. On the single pilot the validity-aware policy used 4 solves, every-event robust MPC used 15, fixed period used 6, and all three served the same three customers. That is a reduction in solves, not a service improvement, and it is not a statistical result. Unanswered announcements are retried, because a stale release would otherwise leave the customer unconsidered. There is no proved advantage over a matched fixed period beyond avoided solves.

## Recommendation

Keep the certificate, the backup, and the supervisor. They are the right engineering core if a later paper is written as a systems paper, and they stop the controller from executing an uncertified arc.

Do not write Part 3 as a large benchmark campaign whose purpose is to declare SAFE-TIME MPC superior. A small pilot cannot support that sentence, and the theory does not predict a service gain over every-event robust MPC when both use the same certificate.

A revision that could still be a theory paper has to change the problem, not add another heuristic:

1. Prove a certificate for a plant the upper corner does not decide. The serious targets are budgeted arc uncertainty and state-of-charge-dependent charging. Both already have routing papers. A contribution would have to beat those certificates on conservatism or cost, with a proof, on a plant the simulator actually runs.
2. Or prove closed-loop feasibility for non-interruptible arcs plus hard preemption plus acceptance, including the case where the backup itself expires during the solve. Proposition 4 stops at the idle vehicle.

Until one of those exists, the accurate description is: a receding-horizon electric-routing controller with an exact rectangle check, a committed backup, and a hard solver deadline, assembled from known pieces and checked on exact toys.
