# Phase 3F — Mechanism definition

**Gate decision: `REVISE`**

Parent SHA: `3da83327`. Holdout frozen. Stochastic-rollout argmax is **retired** as the proposed contribution.

## Scientific posture

Phase 3E showed the prior “proposed MPC” was algorithmically identical to uniform stochastic rollout and lost more often than it won vs B1. Phase 3F prototypes a **different** rule:

**Commitment-viability-aware, baseline-anchored switching MPC**

- Default executable action: persistent **B1** (same seed, ALNS budget, certificate state as the B1 baseline).
- A counterfactual candidate may replace B1 only if:
  1. Nominal **commitment-safety** validation passes (`validate_continuation` + admission sanitizers).
  2. Paired expected improvement \(\mathbb{E}[\Delta]\) over B1 exceeds a **prespecified** threshold (`IMPROVEMENT_THRESHOLD = 0`).
  3. A **prespecified** risk rule holds: every valid paired scenario satisfies \(\Delta_i \ge\) `RISK_FLOOR = 0`.

Hoeffding LCBs on bounded paired deltas are **recorded** under the forecast model (`DELTA_BOUND`, \(\alpha=0.1\)) but are **not** required for switching at \(n=2\) (they are almost never positive). Forecast-model bounds are **never** claimed as guarantees under misspecification.

Thresholds were **not** tuned on Phase 3E seeds.

## Algorithmic distinctness

Unlike unguarded rollout argmax (`CommitmentSafePredictiveMpc`), this controller:

- Anchors every epoch to executable B1.
- Uses **paired** scenario evaluation \(\delta_i = J(a,\omega_i)-J(a_{\mathrm{B1}},\omega_i)\).
- Switches only under explicit safety + improvement + risk gates.

Implementation: `src/safe_time_evrp/mpc_central/switching_mpc.py`, paired interface in `paired_b1_eval.py`.

## Admission-state repair (Task 1)

`Observation.released_open` correctly includes `IN_SERVICE` for visibility, but counterfactuals previously treated those customers as new admits. Repair:

- `eligible_new_accepts` / `sanitize_newly_accepted`
- Ban service visits to `in_service` in `sanitize_routes`
- Validator rejects `illegal_new_accept` and `serves_already_in_service`

Regression reproduces the C1 anomaly at \(t\approx 28.38\) on `A_low_soc_charge` seed 7 and asserts the probe **passes**.

## Novelty honesty

Baseline-anchored safe policy improvement is not new as a *class*. Any top-tier claim would need an EVRP-specific commitment-viability theory with empirical force. This gate tests whether that contribution is ready — see [`PHASE3F_VIABILITY_ANALYSIS.md`](PHASE3F_VIABILITY_ANALYSIS.md) and [`PHASE3F_DECISION_EXPERIMENTS.md`](PHASE3F_DECISION_EXPERIMENTS.md).
