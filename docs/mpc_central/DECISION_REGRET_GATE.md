# Decision-regret gate (Phase 3B)

**Question:** Under **equal scenario-evaluation budgets**, does a commitment-safe, decision-focused (adaptive) allocation recover better first actions than uniform stochastic rollout?

**Not the question:** Does MPC pick a *different* action than rollout?

Artifact: `phase3b_results.json`  
Code: `decision_regret.py`, plant scores via `causal_plant.py`

## References

| Policy | Definition |
|--------|------------|
| Exhaustive truth | Expected plant value of every candidate first action on every scenario (tiny forks only) |
| Reactive | Rank by empty-future scenario only |
| Uniform rollout | Round-robin scenario evals across actions |
| Adaptive MPC | Bootstrap then spend remaining evals on uncertain top-2 rankings |

## Headline (budgets 3 / 6 / 9)

| Metric | Value |
|--------|-------|
| Matched adaptive-vs-uniform cells | 9 |
| Adaptive lower regret | **2** |
| Uniform lower regret | **0** |
| Ties | **7** |
| Verdict | **GO_PROTOTYPE** |

Tight budgets (3 evals) are where adaptive wins: Case A recovers `charge_first`, Case B recovers `reject_now`, while uniform still selects the reactive-looking action. At budgets 6–9 both recover the exhaustive-best action (ties).

## Interpretation

- This is **decision quality per unit of evaluation budget**, not ALNS speed.  
- Wins are on **hand-designed microscopic plant forks** — necessary for a mechanism signal, not a paper campaign.  
- Adaptive computation allocation is established elsewhere; EVRP-specific value still requires matched baselines (Jiang / Sivagnanam / …) at larger scale.  
- **Stop before Phase 4 large controller** until CI is green and this prototype signal is preserved under adversarial nonanticipativity tests (done) and fulfillment auditing (see fulfillment audit JSON).

## Publication stance

`GO_PROTOTYPE` means: proceed to a **small** Phase-4 plant-facing predictive controller that exposes the same adaptive allocation API — not that the paper claim is ready.
