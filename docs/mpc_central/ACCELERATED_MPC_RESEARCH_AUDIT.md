# Accelerated MPC research audit

**Branch:** `research/commitment-safe-predictive-mpc`  
**Verdict: NO-GO** (for the current proposed predictive mechanism as a superiority claim)  
**Artifact:** [`accelerated_results.json`](accelerated_results.json)

## Checkpoint answers

### 1. Are causal scenario rollouts now physically correct and independently replay-valid?

**Mostly repaired; contracts hardened.**

| Issue | Fix |
|-------|-----|
| Busy vehicles teleported to future anchors at current clock | Restored at **current** node/SOC with remaining noninterruptible completion event (`scenario_rollout.seed_simulator_from_observation`) |
| Forced AU at short horizons | Terminal scoring uses residual-feasible probe; feasible unfinished work is **not** charged the 250 AU penalty |
| Announcement = ready-time gaps | Forecast releases use preregistered Poisson `announcement_mean`; `ready`/`due` remain service windows |
| Invalid rollouts looking high-value | Failed independent replay → value forced to `-1e9` |

Regression tests: mid-travel clone vs plant arrival SOC/node; horizon residual treatment; announcement≠ready (`tests/test_accelerated_mpc.py`).

**Remaining limitation:** fork logs use `fork_seed` markers; busy-epoch reconstruction is best-effort from public `VehicleView` (no hidden plant internals). Quiescent epochs remain the preferred comparison setting.

### 2. Does the live MPC actually generate different safe first actions?

**Yes.** Counterfactual generator (`counterfactual_actions.py`) produces accept/reject, charge-now, wait/idle, commit-only, plus ALNS/insertion baselines; deduped by `FirstActionKey` (executable first legs, not solver names). Diversity gate passed on all 6 development cases (`valid_commitment_safe ≥ 2`).

### 3. Does forecasting improve decisions against a forecast-blind policy?

**Not on this matrix.** `proposed_mpc` vs `no_forecast_ablation` does not establish a forecast-driven service gain (and proposed is weak overall). Forecast change is therefore not yet shown to alter admission/charging beneficially in closed loop.

### 4. Does the proposed MPC beat standard stochastic rollout with the same candidates?

**No.** With identical counterfactual candidate sets, `proposed_mpc` (paired-CRN label) and `stochastic_uniform` tied on completed customers in every case. Formal difference collapses to scenario-index order / labeling — **not a new optimality criterion**.

### 5. Can all accepted commitments be protected under stated nominal assumptions?

**B1-style validation remains the commitment gate.** Predictive selection only among candidates that pass independent `validate_continuation`. This is nominal physics only — not robust recursive feasibility.

### 6. Is there a defensible new mathematical/algorithmic idea vs existing research?

**Not yet.** See novelty table below. Current object is a composition of known pieces (commitment validation + stochastic rollout + proactive charge/accept candidates). Jiang–Zhang–Puchinger already cover stochastic DEVRP with proactive charging and rollout/DQN; Sivagnanam et al. cover hard service promises with continual routing; Basso et al. cover safe RL for stochastic EVRP.

### 7. Smallest next step toward a publication-quality experiment?

1. Diagnose **why** counterfactual MPC under-serves vs B1 (over-rejection / wait bias from residual scoring).  
2. Restrict comparisons to decision epochs where charge vs serve or accept vs reject first legs **actually differ** in the chosen plant action.  
3. Only after a reproducible first-action win vs B1 **and** vs identical-candidate stochastic rollout, expand the matrix — still not holdout.

## Threat-to-novelty table

| Prior work | Already covers | Our potential wedge (unevaluated) |
|------------|----------------|-----------------------------------|
| Jiang, Zhang & Puchinger, *Transportation Science* (DOI 10.1287/trsc.2025.0476) | Stochastic requests, proactive charging, perfect-information rollout, DQN | Exact multi-EV commitment preservation + independent replay plant |
| Sivagnanam et al., ICCPS 2026 | Prompt confirmation, preserving promises, continual routing | Joint charge/admit/wait counterfactuals under battery physics |
| Basso et al., TRE | Safe RL for dynamic stochastic EV routing/charging | Model-based MPC with certified nominal continuations |
| Cao et al., EJOR 2025 / OCBA-style R&S | Adaptive simulation-budget allocation | Not our claim — order-fragile adaptive sampler already REVISE/NO-GO |

## What is supported vs unproved

**Supported:** validity repairs; distinct safe first actions; honest matched pilot; no fabricated win.  
**Unproved / rejected for now:** predictive superiority; forecast value; novelty of the argmax; holdout generalization.

## Decision

**NO-GO** for treating the current predictive/counterfactual MPC as the paper’s empirical contribution.  
**Keep** the plant, B1/M1 stack, and repaired rollout contracts as infrastructure. Next work must fix decision quality (when MPC chooses differently from B1, it must be for defensible reasons and with better outcomes), not more sampling heuristics.
