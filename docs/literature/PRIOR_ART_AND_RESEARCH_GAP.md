# Prior art and the research gap

Date of this review: 5 November 2026.

This note records what was actually read. Robust MPC, self-triggered MPC, feasible backup controllers, and anytime routing are established subjects. None of them is treated here as a new idea. The open question is whether a distinctive electric-vehicle mechanism is worth proving in Part 2, after the Part 1 simulator and baseline exist.

## Schneider, Stenger and Goeke (2014)

- Citation: Michael Schneider, Andreas Stenger, and Dominik Goeke. The electric vehicle-routing problem with time windows and recharging stations. *Transportation Science* 48(4), 500–520, 2014. DOI: [10.1287/trsc.2013.0490](https://doi.org/10.1287/trsc.2013.0490).
- What was verified: the publisher abstract, plus the author-deposited instance readme and all 92 instance files (DOI [10.17632/h3mrm5dhxw.1](https://doi.org/10.17632/h3mrm5dhxw.1)). The full journal PDF was not retrieved in this session.
- Problem: static E-VRPTW. A fleet delivers to customers with demands, hard time windows, and service times, may recharge at stations, and returns to the depot. The deposited readme defines Euclidean distance, constant speed, energy `r * distance`, and recharge time `g` per unit of energy.
- MPC: no. The abstract describes a hybrid variable-neighborhood search with tabu search.
- Uncertainty: none in the problem statement that was verified.
- Computation limits: no decision deadline or anytime certificate in the abstract.
- Feasibility: heuristic search. No recursive-feasibility claim was available from the abstract.
- Accepted customers: the problem is static. Every customer is known and the usual goal is to serve them.
- Experiments: newly designed E-VRPTW instances and related benchmarks. The deposit used here contains 92 files: 56 full instances and 12 each of the 5-, 10-, and 15-customer subsets.
- Overlap: this is the physical benchmark our simulator implements. It is not a dynamic controller.

## Desaulniers, Errico, Irnich, and Schneider (2016)

- Citation: Guy Desaulniers, Fausto Errico, Stefan Irnich, and Michael Schneider. Exact algorithms for electric vehicle-routing problems with time windows. *Operations Research* 64(6), 1388–1405, 2016. DOI: [10.1287/opre.2016.1535](https://doi.org/10.1287/opre.2016.1535).
- What was verified: the publisher abstract and the RePEc abstract. The full paper was not retrieved.
- Problem: four static variants: one or several recharges per route, and full or partial recharges.
- MPC: no. Branch-price-and-cut with labeling algorithms.
- Uncertainty: not in the abstract.
- Computation limits: exact solves, not a real-time deadline.
- Feasibility: proven feasible or optimal when the exact algorithm finishes. The abstract reports solves with up to 100 customers and 21 stations.
- Accepted customers: static.
- Overlap: partial recharging and multiple recharges are already classical. Part 1 implements full recharge as the 2014 default and linear partial recharge as a separate policy. It does not claim either as new.

## Basso, Kulcsár, Sanchez-Diaz, and Qu (2022)

- Citation: Rafael Basso, Balázs Kulcsár, Ivan Sanchez-Diaz, and Xiaobo Qu. Dynamic stochastic electric vehicle routing with safe reinforcement learning. *Transportation Research Part E* 157, 102496, 2022. DOI: [10.1016/j.tre.2021.102496](https://doi.org/10.1016/j.tre.2021.102496).
- What was verified: the author manuscript PDF.
- Problem: dynamic stochastic EVRP for one vehicle. Some customers are known at departure. Others arrive with a known probability while the vehicle is en route. Energy on a road stretch is random with a known normal model. The vehicle must return to the depot. The paper assumes requests are accepted and can be served, and that total demand fits in the payload.
- MPC: no. The method is safe Q-learning with lookup-table value approximation, a chance constraint (the manuscript uses 5% as an example), and a second safety layer that tries to keep a charger reachable. The benchmark is deterministic reoptimization by nearest-neighbor construction plus tabu search on expected energy.
- Uncertainty: stochastic requests and stochastic energy. The online reoptimizer plans with expected energy.
- Computation limits: runtime is discussed, including that a MILP reoptimization would be too slow, but there is no hard decision-time certificate.
- Feasibility: chance constraint plus a lookahead energy margin. The manuscript is explicit that a probabilistic policy can still fail, which is why the second layer exists. This is not a recursive-feasibility theorem for an MPC law.
- Accepted customers: all realized requests are supposed to be served. Rejection is not the decision.
- Experiments: 50 instances in central Luxembourg, 25 with 10 customers and 25 with 20, one vehicle, two chargers, energy coefficients from an earlier high-fidelity model. Training used 500,000 episodes in the reported comparison; evaluation used 20,000 episodes.
- Overlap: this is the closest energy-and-request uncertainty paper. It is single-vehicle reinforcement learning, not multi-vehicle MPC, and it does not treat computation deadlines or commitment rejection.

## Jiang, Zhang, and Puchinger (2026)

- Citation: Junyu Jiang, Jian Zhang, and Jakob Puchinger. Dynamic electric vehicle routing problem with stochastic requests. *Transportation Science*, published online 19 October 2026. DOI: [10.1287/trsc.2025.0476](https://doi.org/10.1287/trsc.2025.0476).
- What was verified: the publisher abstract only. The full text and the online appendix were not retrieved. Statements below that are not in the abstract are not claimed.
- Problem, from the abstract: dynamic EVRP with stochastic requests and proactive charging. The vehicle optimizes the route and energy use to maximize the number of served requests, subject to battery capacity and a depot deadline.
- MPC: not under that name. The abstract says the model is a route-based Markov decision process, solved by a perfect-information rollout policy and by deep Q-learning.
- Uncertainty: stochastic requests. The abstract also reports experiments with inaccurate demand prediction. Energy uncertainty is not stated in the abstract that was retrieved.
- Computation limits: the rollout has acceleration mechanisms, and the learned policy is faster online. The abstract reports more than a 50% reduction in online computation time and up to 5.3% better decision quality than the best benchmark they name (value function approximation and rollout). That is an experimental timing result, not a deadline certificate.
- Feasibility: battery capacity and a depot deadline are constraints. No recursive-feasibility theorem is stated in the abstract.
- Accepted customers: the objective is to maximize served requests. The abstract does not describe an irrevocable acceptance commitment.
- Overlap: stochastic dynamic EV routing with partial proactive charging and online lookahead. The method family is rollout and deep Q-learning, which Part 1 deliberately does not implement.

## Sivagnanam, Mukhopadhyay, Samaranayake, Dubey, and Laszka (2026)

- Citation: Amutheezan Sivagnanam, Ayan Mukhopadhyay, Samitha Samaranayake, Abhishek Dubey, and Aron Laszka. Dynamic vehicle routing problem with prompt confirmation of advance requests. ICCPS 2026. Author PDF and arXiv:[2603.07422](https://arxiv.org/abs/2603.07422). Publisher DOI recorded from the search result: [10.1109/iccps68698.2026.00012](https://doi.org/10.1109/iccps68698.2026.00012).
- What was verified: the author PDF of the conference paper, not only the abstract.
- Problem: dynamic dial-a-ride style routing for advance requests. The agency must confirm or reject quickly and then keep improving routes for accepted requests. The vehicles are not electric.
- MPC: no. Prompt insertion for acceptance, plus anytime simulated annealing between requests. A neural value function trained by reinforcement learning scores insertions.
- Uncertainty: demand arrives over time. No battery model.
- Computation limits: experimental time budgets are used (insertion is fast; continual optimization and a competing method are given seconds-per-epoch budgets, including 30 seconds in one comparison). Those budgets are experimental settings, not proved deadlines.
- Feasibility: an accepted request is kept in the route. The paper's claim is algorithmic maintenance of that promise, not a control-theoretic invariant under energy disturbance.
- Experiments: a U.S. microtransit feed and an NYC comparison, five episodes in the reported rejection-rate figures.
- Overlap: prompt commitment plus continual optimization is the closest commitment mechanism. It has no battery, no road-dependent energy, and no MPC terminal set.

## Control results that are already established

These papers were retrieved as PDFs. They are cited so that Part 2 does not rediscover them.

- Florian David Brunner, Maurice Heemels, and Frank Allgöwer. Robust self-triggered MPC for constrained linear systems: a tube-based approach. *Automatica* 72, 73–83, 2016. At each sample the controller returns both the next sample time and the inputs until then. Tube tightening gives robust constraint satisfaction. The next trigger is computed in advance. This is self-triggered MPC, not event-triggered MPC, and it is for linear systems rather than routing.
- Zhongqi Sun, Li Dai, Kun Liu, Dimos V. Dimarogonas, and Yuanqing Xia. Robust self-triggered MPC with adaptive prediction horizon for perturbed nonlinear systems. Author PDF `Sun_TAC19.pdf`. The controller chooses the next trigger and shortens the horizon near a terminal set. Recursive feasibility and input-to-state stability are proved for the system class in the paper. The plant is not a vehicle-routing state.
- Alberto Bemporad, Daniele Bernardini, and Panagiotis Patrinos. A convex feasibility approach to anytime model predictive control. arXiv:1502.07974, 2015. A feasibility solver can be stopped early and still enforce a terminal-set condition, while extra CPU time improves the cost. The setting is convex linear MPC, not a combinatorial route.

Event-triggered control, as distinguished in the Brunner and Sun papers, checks a condition on the measured state. Self-triggered control commits to the next update time at the current update. Part 1 implements neither theory. It reoptimizes on routing events and on a fixed maximum interval.

## What is not new

The following already exist, in the papers above or in the control literature those papers review:

- receding-horizon replanning
- robust constraint tightening and tube MPC
- self-triggered and event-triggered MPC with recursive feasibility for linear or nonlinear plants
- anytime MPC that keeps a feasible incumbent when optimization stops early
- chance constraints on battery depletion
- partial and multiple recharges in static EVRP
- prompt accept/reject decisions with later route improvement
- rollout and reinforcement learning for dynamic EV routing

## Questions that remain specific enough for Part 2

A useful Part 2 result would have to use the EVRP structure, not restate the papers above. The mathematical questions that still look open, and that this codebase can host, are:

1. Which terminal condition is checkable for a vehicle that is already on a noninterruptible arc, carrying freight for accepted customers, when arc energy lies in a known interval rather than at the nominal value `r * distance`?
2. When does that condition remain feasible after one executed arc and one partial recharge, without assuming that a new optimization problem will be solved to optimality?
3. How should a self-triggered update time be computed from the energy margin and the time windows of accepted customers, rather than from a linear feedback law?
4. If the optimizer may be stopped at a deadline, which incumbent is allowed to replace the previous suffix without dropping an accepted customer or starting an arc that has no feasible continuation under the energy interval?
5. Which of those statements survive route-dependent bounds (slope, traffic, temperature) once an energy model is actually calibrated, as opposed to a uniform design margin?

Part 1 does not answer these questions. The nominal controller can report `no_feasible_continuation`. That flag is an empirical failure of the heuristic, not a proof of infeasibility, except on the enumerated toy family.

## Consequence for this repository

The nearest competitors are Basso et al. (safe learning under energy and request noise, one vehicle), Jiang et al. (stochastic-request EV routing with rollout and deep Q-learning; abstract only), and Sivagnanam et al. (commitments and anytime improvement, no battery). A paper that only combines those three labels would not be a contribution. Part 2 has to prove a property that uses noninterruptible travel, charging time, time windows, and accepted customers together.
