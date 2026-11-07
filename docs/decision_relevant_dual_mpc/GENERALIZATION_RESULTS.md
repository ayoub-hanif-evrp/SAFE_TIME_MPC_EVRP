# Generalization results

Artifact: `generalization_results.json`  
Generator: `python -m safe_time_evrp.dr_dual.compute_study`

## Fleet information value (Milestone 1)

### Legacy two-EV network

Charge-route travel energy weakly dominates direct under both \(\theta\) (5≤5 and 7≤8), both feasible under battery 14. Controlled share vs no-share comparison with fixed EV1 informative travel:

| Metric | Value |
|--------|-------|
| \(V_{\mathrm{shared}}\) | 5.7 |
| \(V_{\mathrm{without}}\) | 5.7 |
| \(\Delta\) VoI | **0** |

Contingent route **labels** may still differ in other oracles; **expected EV2 reward does not**.

### Positive-VoI network (`make_two_ev_positive_voi`)

Tight battery (8): direct feasible only for \(\theta=0\); charge needed for \(\theta=1\); charge detour strictly costlier for \(\theta=0\). Sharing yields DIRECT/CHARGE by \(\theta\); without sharing, robust CHARGE. \(\Delta\) VoI \(>0\) (strict).

## Observation-timing bound (Milestone 2)

See `OBSERVATION_TIMING_THEOREM.md`. Empirically: OTUB ≥ \(Q^\star\) and OTUB ≤ DRUB on uninformative baseline exploit.

## Suite compute (Milestone 5)

Eight preregistered instances vary battery, deadlines, charge speed, observation timing, first-action count, energy cost, and \(\theta\)-separability — not “useless+2”.

Summary (committed artifact):

- Exact first-action agreement for clairvoyant / REUB_v1 / OTUB / combined: **8/8**
- Instances where pruning **strictly reduced** total heavy ops vs unpruned: **0/8** for every bound mode

Interpretation: sound pruning of decoys exists, but bound construction cost dominates on these sizes. **No paper-level scalability claim.**

## Dynamic announcements / depot return

`generic_small.run_dynamic_announcement_demo` exercises announce→accept→serve and optional depot return when flagged. Default exact continuation family still does not *require* depot return unless explicitly executed.
