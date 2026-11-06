# Prior-art threats (Gate 3A)

Evidence labels: **FT** = full text or long preprint read this gate; **ABS** = abstract / secondary summary; **REPO** = already audited in this repository.

## Closest methods

| Paper | Evidence | Core method | Dynamic requests? | Multistage causal routing? |
| --- | --- | --- | --- | --- |
| Han et al. (2025), TRE | ABS (+ methods description from prior gate) | Two-stage adaptive robust EVRP; route-dependent uncertainty; adjustable charge and service starts; bidirectional labeling | No (static) | No (first-stage routes fixed) |
| Jeong et al. (2024), TRC | FT manuscript previously | Two-stage ARO energy uncertainty; adjustable recharge; C&CG heuristic | No | No |
| Spinelli et al. (2026), TRC | FT arXiv `2506.19426` | Two-stage stochastic; fixed customer sequence; threshold charging recourse | No | Recourse is charge detours on a fixed sequence, not free route forks after partial observation |
| Erdelić et al. (2026), CIE | ABS | Time-dependent EVRP; SOC-dependent charge; ALNS | No | N/A (deterministic TD) |
| Jiang, Zhang, Puchinger (2026) | ABS | Dynamic EVRP / MDP / DQN / lookahead | Yes | Learning rollout, not robust multistage certificate |
| Sivagnanam et al. (2026) | FT (Part 1) | Prompt confirmation + anytime SA | Yes | Not electric; no battery uncertainty budget |
| Carpentier, Chancelier, De Lara (2024) | ABS | Time consistency in multistage stochastic optimization | General OR | State augmentation for time consistency is **known** — not standalone novelty |
| FPTAS robust multistage (IJOC 2024) | ABS | Adaptive robust multistage under budgeted uncertainty | General | Complexity/approx results; not EVRP commitments |
| This repo Part 2/2.5 | REPO | Rectangle certificate; backup; deadline; validity trigger | Yes (sim) | No true multistage predictive horizon |

## Axis-by-axis comparison

1. **Static vs dynamic requests.** Han/Jeong/Spinelli/Erdelić are static planning models. Jiang and Sivagnanam are dynamic. Our hypothesis is dynamic **with irrevocable accepted commitments** under physical uncertainty — closer to Sivagnanam’s commitment idea plus EV energy, not Han’s static ARO.

2. **Open-loop vs adaptive routing.** Han adapts **charge amounts and start times** on a **fixed** first-stage route. Spinelli adapts charging detours on a fixed customer sequence. Neither is a causal policy that may change the next customer/station after observing a prefix of disturbances.

3. **One-stage / two-stage / multistage.** Han and Jeong are two-stage ARO. Spinelli is two-stage stochastic. True multistage feedback (decision after each revelation, nonanticipative) is the structure we probe.

4. **Decision timing and observability.** Noninterruptible arcs and station-arrival SOC for charging are plant constraints in this repo. Han’s adjustable charge assumes wait-and-see after route uncertainty on that route, not online MPC with locked actions.

5. **Rectangular vs budgeted uncertainty.** Part 2 used rectangles. Han uses route-dependent budgets. Gate 3A uses an explicit residual budget on physical transitions and tests illegal reset.

6. **Coherence after replanning.** Time-consistency literature warns that naively rebuilding sets at each stage can change the contract. Carpentier et al. make residual information part of the state — **known**. Our question is whether an **EVRP-specific** terminal viability rule with commitments + adaptive charge + residual \(\Gamma\) is new and useful, not whether residual state exists.

7. **Fixed vs adaptive charging.** Case P (Part 2.5) shows fixed partial targets are not monotone. Han/Jeong already use adjustable charging. Adaptive charge alone is **not** novelty.

8. **Irrevocable accepted deliveries.** Sivagnanam has confirmation without electricity. Robust EVRP papers typically optimize a static customer set. Online acceptance under residual budget is the commitment layer we add.

9. **Closed-loop feasibility.** Generic MPC backup principles are known. Part 2.5 concluded skip-while-valid is not a new theorem. Gate 3A asks for a **terminal continuation** tied to multistage residual-budget viability.

10. **Algorithms and complexity.** Labeling / resource extension is classical (Desaulniers et al.). Han’s bidirectional labeling for conservative cost is a direct competitor for any “new certificate” that is only robust resource propagation on a fixed sequence.

## Does Han already solve our intended question?

**No — not as stated for dynamic multistage commitment MPC.**

Han solves: static fleet routes under travel-time and energy uncertainty with a route-dependent budget, with charging quantities and service starts adjustable after uncertainty on that route, estimated via robust labeling / bi-level search.

Han does **not** solve: online irrevocable acceptance; causal **routing forks** after partial disturbance observation; residual-budget conditioning inside a receding-horizon controller; noninterruptible locked actions during compute.

**If Gate B finds only charge-adjustable gains on a fixed sequence, Han already covers the substance → NO-GO for novelty.**

**If Gate B finds a routing-fork instance where open-loop and fixed-sequence two-stage fail but causal multistage feedback succeeds, a literature gap remains for the mechanism — still not a theorem until Gate C.**

### Gate B outcome (recorded)

CEX-1 `routing_fork_commitment` realizes the routing-fork gap: open-loop and Han-style fixed-route two-stage are PROVEN_INFEASIBLE; causal feedback is PROVEN_FEASIBLE. N2 shows charge-only recourse collapses to Han. Gate C did not produce a theorem beyond generic robust DP → overall **NO-GO** (see `RESEARCH_DECISION.md`).

## Combination is not novelty

Residual budget state + adaptive charge + backup MPC keywords do not create a paper. A GO requires a sound EVRP-specific result beyond generic robust DP and beyond Han labeling on fixed routes.
