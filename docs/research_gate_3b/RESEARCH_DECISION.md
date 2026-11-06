# Research decision — Gate 3B

**Decision: REVISE**

Git revision at decision time: `6daaffd` on branch `research/realdata-mpc-gate`.
CI: formatting failures on the prior research branch repaired; full pytest green
locally (60 tests) before push.

## What was established

1. **Oracle validity repaired** (`ORACLE_CORRECTIONS.md`): no false `PROVEN_INFEASIBLE`
   under search caps; budget-exceeding histories excluded; CEX-2 withdrawn; Gate 3A
   routing-fork NO-GO for theorems preserved.
2. **Datasets acquired** (raw not committed): EVRP-TW-D (MD5 verified), LaDe
   `delivery_jl`, Amazon unsigned sample prefixes, ESOGU-ML5EV (MD5 verified).
3. **Feasibility pilot**: under native EVRP-TW-D batteries, NN tour energy exceeds `Q`
   on ~53% of probed instances and charger insertion changes energy feasibility on ~33%.
4. **Falsifiable MPC candidate** retained: scalable feedback MPC that prices future
   routing flexibility while preserving accepted commitments under energy uncertainty —
   challenged by Han/Spinelli, DEVRP PIR/DQN (TS 2025.0476), AMoD MPC, and Gate 3A DP
   collapse (`LITERATURE_NOVELTY_THREATS.md`).

## Why not GO

- Published EVRP-TW-D **archive does not contain road networks** despite metadata
  (2-norm Solomon/pickle only). A top-tier “real-world EVRP” claim is not yet grounded.
- No empirical win vs serious online EVRP baselines yet (explicitly out of scope for this
  gate’s “no large campaign” rule).
- No new theorem (correctly refused after Gate 3A).

## Why not NO-GO

- Energy/charging are not inert under native instance parameters.
- Demand (LaDe) and energy (ESOGU) evidence streams exist with clear non-combinability
  rules.
- A concrete falsifiable control mechanism remains after literature threats.

## Required revision before Part 3

1. Resolve geometry: obtain true road-network EVRP layers **or** reframe the paper as
   semi-synthetic 2-norm EVRP-TW-D + real demand processes (no OSM claim).
2. Train/dev/held-out protocol on scales/splits with **versioned** vehicles near native
   `Q` (avoid ≤25% battery tricks).
3. Implement the flexibility-aware feedback MPC and compare to open-loop RH, fixed-route
   charge recourse, myopic insertion, and at least one DEVRP-style rollout/DQN baseline
   on held-out instances — without theorem inflation.

## Exact contribution still needed

A **demonstrable present-action change** from predictive flexibility valuation under
energy uncertainty that improves commitment-feasible service versus those baselines for a
reason that is not “we ran robust DP on a toy.”

Part 3 experiments are **not** started by this gate.
