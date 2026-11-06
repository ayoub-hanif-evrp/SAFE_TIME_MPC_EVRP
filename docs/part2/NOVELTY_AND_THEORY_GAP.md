# Novelty and theory gap

A combination of a robust routing check, a backup route, a deadline, and a trigger is not a new contribution. This note says what was read, what is already known, and which narrower statement is actually proved in this repository.

## Evidence labels

| Source | What was read | Label |
| --- | --- | --- |
| Jeong, Ghaddar, Zufferey, and Nathwani (2024), [10.1016/j.trc.2024.104529](https://doi.org/10.1016/j.trc.2024.104529) | Author manuscript via arXiv `2204.10913` and the UNIGE deposit | Full-text manuscript, not the published typeset PDF |
| Han, Yan, Chi, and Park (2025), [10.1016/j.tre.2025.104211](https://doi.org/10.1016/j.tre.2025.104211) | Publisher abstract and the IDEAS/RePEc abstract | Abstract only |
| Jiang, Zhang, and Puchinger (2026), [10.1287/trsc.2025.0476](https://doi.org/10.1287/trsc.2025.0476) | Abstract from Part 1 | Abstract only |
| Basso et al. (2022), [10.1016/j.tre.2021.102496](https://doi.org/10.1016/j.tre.2021.102496) | Author manuscript read in Part 1 | Full-text manuscript |
| Gräfe and Trimpe (2025), [10.23919/ECC65951.2025.11187035](https://doi.org/10.23919/ECC65951.2025.11187035) | arXiv `2504.19540` | Full-text preprint |
| He et al., predictive-triggered MPC (2025), [10.1109/TIE.2025.3579095](https://doi.org/10.1109/TIE.2025.3579095) | Publisher abstract | Abstract only |
| Sivagnanam et al. (2026), [10.1109/ICCPS68698.2026.00012](https://doi.org/10.1109/ICCPS68698.2026.00012), code [DVRP-AR](https://github.com/aronlaszka/DVRP-AR) | Author PDF read in Part 1 | Full text. The method is not electric. |
| Erdelić, Đurasević, Erdelić, and Carić (2026), [10.1016/j.cie.2025.111758](https://doi.org/10.1016/j.cie.2025.111758) | ACM abstract and the published abstract | Abstract only |
| Desaulniers, Errico, Irnich, and Schneider (2016) | Abstract only, from Part 1 | Resource-extension functions for EVRP are prior art |
| Brunner, Heemels, and Allgöwer, Automatica (2016); Sun et al., TAC (2019) | Known self-triggered MPC results, from Part 1 | Full texts were not re-fetched for Part 2 |

Nothing below invents a theorem, a table, or a percentage that those sources do not state.

## What is already known about robust EVRP?

Jeong et al. formulate a two-stage adaptive robust EVRP with time windows, en-route partial charging, and an energy-consumption uncertainty set. First-stage routes are chosen before the consumption is known. Charging can adapt. They minimize worst-case energy and enforce windows and battery limits. The algorithm is column-and-constraint generation with variable-neighborhood search, not MPC.

Han et al., from the abstract, treat uncertain travel time and energy together. Routes are fixed in the first stage. Charging amounts and service start times adapt. Uncertainty of a route depends on how many arcs it uses. They estimate a conservative cost with bidirectional labeling. That is a robust resource calculation for a fixed route.

A 2026 stochastic EVRP with a recharge threshold (Transportation Research Part C, 10.1016/j.trc.2025.105480, abstract only) uses scenarios and recourse rather than a hard rectangle.

So robust energy-aware routing, adaptive charging, and conservative labeling of a fixed route are established. They are offline or two-stage routing papers, not receding-horizon controllers with non-interruptible actions.

## What is already known about safe backups and feasibility certificates?

EVRP labeling algorithms propagate time, load, and battery along a fixed sequence and reject a label that cannot be extended (Desaulniers et al.; Han et al. from the abstract). For monotone resource windows, an upper travel time and an upper energy consumption are the usual worst case. That test is sufficient, and under independent rectangular bounds and linear charging it is also necessary. Calling the upper-corner simulation a certificate does not create a new test.

Safe reinforcement learning for one electric vehicle (Basso et al.) uses a chance constraint and a backup inside the learning loop. It is not a worst-case route certificate and it is not multi-vehicle MPC.

A stored feasible incumbent that is reused when a heuristic fails is standard. Part 1 already does this and labels it as a heuristic.

## What is already known about self-triggered MPC?

Self-triggered and event-triggered MPC have recursive-feasibility and stability proofs for linear and nonlinear systems with bounded disturbances (Brunner, Heemels, and Allgöwer; Sun, Dai, Liu, Dimarogonas, and Xia). The trigger depends on the predicted tube and the cost, not on a vehicle-routing commitment.

Gräfe and Trimpe prove a robust event-triggered MPC that, at each step, optimizes only a fixed-size subset of systems. The priority is the distance between the measured state and the predicted state. Constraint tightening grows with the time since the last solve. The plant is a set of nonlinear systems (quadcopters in the experiment), not a routing graph.

The predictive-triggered MPC abstract says the optimization is started early, in parallel, so that a nonzero solve time does not have to be idealized as zero, and that feasibility and stability are proved for that construction. The abstract does not mention routing, batteries, or customer commitments.

## What is already known about anytime vehicle routing?

Sivagnanam et al. accept customers with an explicit confirmation and keep improving the route by simulated annealing until a time limit. A late improvement cannot revoke a confirmation. Their vehicles are not electric. Anytime MPC for convex problems is older (Bemporad, Bernardini, and Patrinos). A deterministic insertion loop with a feasible incumbent is a simple case of that idea.

Erdelić et al., from the abstract, solve a time-dependent EVRP whose charging time depends on the state of charge, with a MILP for small instances and ALNS plus an exact station-placement routine. They also report that linearizing travel time made more than 69 percent of the related solutions infeasible. That is a warning against exporting a monotone interval certificate to time-dependent speeds. This Part 2 certificate does not claim that case.

## What is unresolved in the interaction?

The open question is not "can a fixed EV route be checked under energy uncertainty?" and not "can MPC be event-triggered?"

The interaction that is not settled by those papers is:

- a non-interruptible electric route already in motion,
- an irrevocable service commitment,
- a hard kill of the optimizer,
- and a rule for when a new solve is required for safety rather than for cost.

No paper in the list above states a theorem with all four. That absence is not itself a theorem.

## What mathematical result would be nontrivial?

Two alternatives were considered and are not claimed.

**Budgeted uncertainty.** If at most a few arcs may attain their upper bound, the independent upper corner is not an admissible realization. A certificate then has to search the budget, which is the direction of Han et al. Implementing that search would reproduce their robust routing model. It is not a new MPC theorem. Stop.

**Non-monotone charging or time-dependent speed.** Erdelić et al. already show that a linearized time model can certify a route the time-dependent model cannot execute. A sound certificate for that plant would be nontrivial. This repository's plant is the linear Schneider model, so that theorem cannot be proved here without changing the plant. Stop.

The result that matches the implemented plant is narrower and mostly already implied by monotone resource extension:

> For a fixed sequence, fixed charge targets, and independent rectangular bounds on the Schneider linear model, the route is robustly feasible if and only if the upper-corner simulation is feasible. After one realized arc inside the rectangle, the suffix remains robustly feasible. Rejecting a new request does not change that certificate. Replacing the sequence, accepting a new request, or leaving the rectangle can destroy it.

The proof is in `FEASIBILITY_PROOFS.md`. It is a specialization, not a new extension function. The prefix cache in the code is the standard one and is not claimed as new.

## What would make a method substantially different?

A substantially different method would need at least one of these, proved for the plant that is actually simulated:

- a certificate that is exact on a non-rectangular or non-monotone energy model and cheaper or less conservative than labeling,
- a closed-loop theorem that includes solver preemption, non-interruptible arcs, and new acceptances,
- or a trigger with a proved service guarantee that beats a matched fixed schedule for a reason other than "the backup was already safe, so we skipped solves."

Part 2 establishes the first bullet only for the linear rectangle, where the upper corner is the classical test. It does not establish the second or the third. The implementation separates the backup from the candidate and kills a late process. That is an engineering invariant. It is the right invariant, and it is not a new control theorem.

## Closest papers

For the certificate: Han et al. (2025), abstract only, and the EVRP labeling literature.

For computation limits: Gräfe and Trimpe (2025), full preprint.

For commitments and anytime decisions: Sivagnanam et al. (2026), full text, not electric.

None of these is an implementation of this controller. None of them leaves the statement above unproved in their own setting. The gap that remains is the joint closed loop, and this part does not close it.
