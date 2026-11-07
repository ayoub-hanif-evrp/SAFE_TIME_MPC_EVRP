# Gate 3F — Research decision

## Verdict: **REVISE**

## Split reading

| Layer | Status |
| --- | --- |
| Experimental infrastructure (items 1–5) | **Ready enough** for a later mechanism gate |
| Commitment-MPC hypothesis specificity | **Not yet sharp enough** to authorize implementation |

## Checklist

| # | Requirement | Status |
| ---: | --- | --- |
| 1 | Correct Poisson announcements; announcement ≠ due clamp; offline UB | Met |
| 2 | Forecast noninterference; `build_scenarios_for(instance)` quarantined | Met |
| 3 | Duplicate-assignment + budgeted robust commitment checks | Met (empirical gate, not a theorem) |
| 4 | Plant-time stale discard contract tested | Met (optional flag; no hard RT claim) |
| 5 | Amazon no silent widen; EVRP-TW-D integration workflow | Met |
| 6 | Middle operating regime on EVRP-TW-D | Met (n=4, UB≈0.70; RH≫myopic; flex≡rollout) |
| 7 | Nontrivial mechanism distinction ready to code | **Not met** — hypothesis still adjacent to ADP/scenario lookahead without a chosen sound-bound or certified frontier claim |

## Decision rule application

- Not **GO** to mechanism implementation: criterion 7 fails.
- Not **NO-GO** on the EVRP-MPC line: trustworthy middle-regime episodes exist; anticipation (RH vs myopic) matters; flexibility remains a negative control.
- **REVISE:** keep the Gate 3F platform; refine the commitment-cost claim until a nontrivial distinction is explicit; **do not** implement a new controller or Part 3 in this gate.

## Explicit non-claims

- Not stochastic scenario-tree MPC.
- Not a robust recursive-feasibility theorem.
- Not measured ESOGU consumption; energy-active Amazon is modeled uplift with synthetic depot charging.
