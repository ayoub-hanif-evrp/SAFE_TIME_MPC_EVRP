# Phase 3F — Commitment viability analysis

## Resource definitions (witness-based)

From a **validated nominal continuation witness**:

| Resource | Definition under simulator assumptions |
|----------|----------------------------------------|
| Window slack | \(\min_c (\mathrm{due}_c - t^{\mathrm{end}}_{\mathrm{route}})\) over planned services (conservative proxy) |
| End SOC | Minimum end-of-route SOC across vehicles |
| Charge time | Total planned charge duration in the witness |
| Load residual | Capacity minus (current load + planned service demand) |

Assumptions: nominal linear energy, Euclidean arcs, noninterruptible locked actions, no station-capacity contention in the plant.

These certify residual resources **of that plan**, not disturbance-robust recursive feasibility.

## Empirical probe

On `A_low_soc_charge` seed 7 at the first public decision epoch, witness residual-resource dominance **disagreed** with causal rollout ranking on at least one action pair (`contribution = DISAGREES_WITH_ROLLOUT`).

Interpretation:

- Residual metrics *can* flag scarce flexibility that expected rollout value alone does not encode on some epochs.
- This is **not** yet a theorem that witness analysis yields a superior switching rule. The switching controller does **not** currently use viability dominance as a hard gate — only commitment feasibility + paired \(\Delta\).

## Proposition (honest)

**What is true:** Under FleetSimulator nominal physics, a validated continuation witness implies immediate commitment coverage for accepted / newly accepted customers and supplies exact residual resource numbers for that plan.

**What is not proved:** That these residuals form a sufficient statistic for recoverable flexibility under future stochastic announcements, or that ranking by residual dominance dominates causal paired \(\Delta\) for closed-loop service.

**Counterexample-class observation (oracle):** On the Case-A charge fork, restricted enumeration prefers `charge_first`, but the paired risk rule (`min_delta ≥ 0`) rejects the switch because one scenario is slightly worse — so viability/rollout signal alone does not automatically produce the nonmyopic charge action under the prespecified risk floor.

## Negative / partial result for the paper claim

Witness analysis contributes a **measurable** EVRP-shaped object beyond binary route feasibility, but Phase 3F does **not** establish it as a decision rule that improves development outcomes. Treat it as a research lead, not a finished differentiator.
