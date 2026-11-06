# Feasibility proofs

This file separates what is proved from what was only run. The plant is the linear Schneider model in `environment/physics.py`. The uncertainty set is the rectangle in `robust/uncertainty.py`.

## Assumptions

- **A1.** Every arc travel time lies in \([\alpha_\tau \tau, \beta_\tau \tau]\) and every arc energy lies in \([\alpha_e e, \beta_e e]\), independently.
- **A2.** The visit sequence and the charge targets are fixed. A full charge targets the battery capacity. A partial charge uses the target written on the visit.
- **A3.** Travel time and energy do not depend on state of charge or payload.
- **A4.** Charge duration is \(g\) times the energy added, so it grows as the arrival state of charge falls.
- **A5.** The vehicle may wait until a window opens. Service must start by the due time. The depot must be reached by its due time.
- **A6.** Demand, capacity, and service duration are deterministic.
- **A7.** Stations stay open, do not queue, and do not change \(g\).

If any of A1–A7 fails, the implementation returns `unknown` or the claim is withdrawn. A3 and A7 are properties of this plant, not facts about electric vehicles in general.

## Lemma 1 (upper corner)

Under A1–A7, the latest clock time and the lowest state of charge along a fixed sequence are attained when every arc uses \(\beta_\tau\) and \(\beta_e\).

**Proof.** Proceed along the sequence. Increasing the travel time on the current arc cannot decrease the arrival time. Increasing the energy cannot increase the arrival state of charge. A later arrival can miss a window or wait; it cannot make a due time easier. A lower arrival state of charge lengthens a fixed-target charge, which can only delay the departure. After a charge the state of charge equals the target, so the battery coupling resets, but the clock coupling does not: the longest charge is the one from the lowest arrival state of charge. Payload does not depend on the factors. Therefore any other realization arrives no later and, before each charge, no lower in state of charge than the upper corner. \(\square\)

## Proposition 1 (exact rectangle)

Under A1–A7, a fixed sequence is feasible for every realization in the rectangle if and only if it is feasible at the upper corner. The implementation's verdict `certified_feasible` or `certified_infeasible` follows that simulation. `certified_infeasible` exhibits the failing corner, which is inside the rectangle, or a missing arc or a missing commitment, which fails for every realization.

**Proof.** Lemma 1 gives necessity of the corner: if the corner is infeasible, that realization is a counterexample, so the sequence is not robustly feasible. If the corner is feasible, every other realization has an earlier or equal clock at each service start and a higher or equal state of charge before each charge, so every window, battery floor, payload check, and depot deadline that holds at the corner holds for that realization. \(\square\)

The inflation mode multiplies \(\beta_e\) by a constant greater than one. Proposition 1 does not apply to it. That mode can reject a corner that is feasible. Case E records one such route. The verdict is then a sufficient condition for a tighter rectangle, not a proof about the original one.

## Proposition 2 (one-arc shift)

Assume A1–A7 and that the sequence is robustly feasible from an anchor. Let the first arc be realized at factors no larger than the upper factors, and let the state of charge stay at least as high as the upper-corner state after that arc. Then the suffix, from the realized anchor, is robustly feasible for every remaining realization in the rectangle.

**Proof.** The realized post-arc state is componentwise no worse than the upper-corner post-arc state: time is smaller or equal, state of charge is larger or equal. Lemma 1 applied to the suffix, starting from a better anchor, still uses the upper factors on the remaining arcs. Those constraints were already satisfied from the worse anchor. \(\square\)

The unit test realizes the first arc at the nominal factor, which is inside a rectangle whose upper factor is 1.2, and re-certifies the return. This is one numerical check of the proposition, not a substitute for the proof.

Proposition 2 does not survive an insertion, a new acceptance, or a factor above the upper bound. Cases A, B, and H are counterexamples to those extensions.

## Proposition 3 (rejection)

If a backup is certified and the controller rejects an announced customer without changing routes, anchors, or \(\mathcal W\), the same certificate remains valid.

**Proof.** The pair \((y, \pi)\) that was certified is unchanged. Announced customers are not obligations of \(\pi\). \(\square\)

Accepting the customer produces a different sequence. Proposition 1 must be applied again. Case A is a sequence that passes a nominal simulation and fails Proposition 1.

## What is not proved

- **Closed-loop re-optimization.** If a later solve replaces \(\pi\), Proposition 2 says nothing until the new sequence is certified from the new anchor. The code enforces that by refusing to commit an uncertified or stale candidate. That is an invariant of the program. It is not a theorem that a feasible candidate will exist.
- **Recursive feasibility in the sense of smooth MPC.** There is no terminal cost, no control-invariant terminal set in a continuous state space, and no argument that the optimizer remains feasible at every future sample. Dynamic routing with a discrete acceptance decision is not that system.
- **New requests.** A request released after the certificate can be rejected without breaking Proposition 3. It cannot be accepted without a new certificate. There is no proof that a feasible insertion exists.
- **Computation.** Proposition 2 assumes the suffix is started from the realized anchor. A solve that finishes against an older action identity is outside the hypothesis. Case D.
- **Disturbances outside \(\mathcal W\).** Case H. The guarantee stops. The failure is reported.

## Empirical checks

The tests compare the propagator with `evaluate_route` on the scaled arc tables for the upper corner. They include a battery insertion that is nominally feasible and robustly infeasible, a window that breaks only under the time factor, a tightened rectangle that is strictly more conservative, a non-monotone flag that stays `unknown`, and a shift inside the rectangle. Those runs support the implementation of Propositions 1–3. They do not extend them.

## Unresolved

An exact certificate for budgeted uncertainty, for state-of-charge-dependent nonlinear charging, or for time-dependent speeds is open here. The literature review stopped after those two alternatives because both are already occupied by routing papers and neither is the plant this code simulates.
