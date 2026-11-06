# Mathematical formulation

Three objects are kept separate. The plant is what the simulator stores. The information state is what a controller is allowed to read. The plan is a proposal plus a certificate. A certificate is not a state of the battery.

## Plant

The plant state at time \(t\) is

\[
x(t) = \bigl(t,\; (p_v, \sigma_v, q_v, \ell_v, a_v)_{v \in V},\; s\bigr).
\]

\(p_v\) is the node or the arc already being traversed. \(\sigma_v\) is the state of charge. \(q_v\) is the payload and the set of customers whose goods are on board. \(\ell_v\) is the non-interruptible action, if any: travel, service, or charging. Waiting may be cancelled. \(s\) maps each customer to hidden, announced, rejected, accepted, dispatched, in service, completed, or accepted but not fulfilled.

The Schneider vector field used here is linear. Arc \((i,j)\) has nominal travel time \(\tau_{ij}\) and nominal energy \(e_{ij}\). A full charge to capacity \(Q\) takes \(g(Q-\sigma)\). Payload changes only when a tour is loaded at the depot and when service starts. This is the plant. It is not a smooth control-affine system, and proofs that need that structure are not invoked.

## Information state

At a decision instant \(t_k\) the controller receives an observation \(y_k\):

- the clock and each vehicle's anchor (the predicted end of the current non-interruptible action, or the current node if the vehicle is idle),
- battery, load, and on-board customers at that anchor,
- customers that have been announced, accepted, completed, rejected, or deferred,
- the current certificate's hypotheses: the rectangle and the backup version.

Hidden release times are not in \(y_k\). A held-out travel-time or energy realization is not in \(y_k\). The observation type has no field for either one.

## Plan and certificate

A plan \(\pi\) assigns each vehicle a finite visit sequence and a charge target on each charging visit. A certificate is a verdict about one pair \((y, \pi)\) under one uncertainty set \(\mathcal W\):

- `CERTIFIED_FEASIBLE` only after the supported check passes,
- `CERTIFIED_INFEASIBLE` only when a realization inside \(\mathcal W\), or a structural contradiction, has been exhibited,
- `UNKNOWN` when the model is outside the supported class.

The backup \(\pi_{\mathrm{backup}}\) is the last plan whose certificate was committed. A candidate can be staged. It becomes the backup only after `commit` with the same action identity. This is an implementation invariant. It is not the same statement as recursive feasibility of every future re-optimization.

## Uncertainty

The supported set is a rectangle. For every arc,

\[
\tau_{ij} \in [\alpha_\tau \tau_{ij},\; \beta_\tau \tau_{ij}], \qquad
e_{ij} \in [\alpha_e e_{ij},\; \beta_e e_{ij}],
\]

with the factors independent across arcs. The state of charge must stay at least \(\underline\sigma\).

| Object | Role |
| --- | --- |
| Nominal \((\alpha,\beta)=(1,1)\) | The benchmark tables. |
| Design rectangle | Factors chosen by the user. Not a confidence interval. |
| Scenario-derived rectangle | Would be computed from traces that the controller is allowed to see. Not fitted in Part 2. |
| Held-out realization | Used only to break the guarantee on purpose (Case H). Never stored as \(\mathcal W\). |

A budgeted set, a correlated set, and a time-dependent speed map are different models. The certificate returns `UNKNOWN` if `monotone_linear` is false.

## Commitments

Acceptance is irrevocable inside the model. On acceptance the controller promises that the committed sequence serves that customer inside the window, for every realization in the current rectangle, together with the customers already accepted. The promise does not cover a later request, a factor outside the rectangle, a station closure, or a change of the charge policy.

If an accepted customer cannot be placed on a certified continuation, the controller must not pretend the old backup still serves them. The status `accepted_unfulfilled` is the end-of-episode record of a broken promise. Rejecting a customer who was only announced does not break a promise. Service is still counted against every announced customer. Acceptance rate and commitment failures are separate numbers. The controller is not allowed to look good by rejecting almost every request without those numbers being reported.

## Timing

A decision occupies plant time equal to its measured wall time, up to the next physical event. If that event occurs during the solve, the candidate is stale and is not committed. The clock does not freeze for the duration of a solve while a physical event is due. Details are in `COMPUTATION_AWARE_MPC.md`.

## Objective

The candidate generator is lexicographic in the same sense as Part 1: cover accepted customers, then insert announced customers, preferring a larger worst-case time margin when several certified insertions exist. It is not a weighted-sum MPC. It is not an exact mixed-integer solver. The certificate, not the generator, decides feasibility.
