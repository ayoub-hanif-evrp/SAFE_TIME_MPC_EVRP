# MPC formulation — Commitment-Safe, Decision-Aware Stochastic MPC for D-EVRP

**Status:** Research hypothesis / problem statement (Phase 1).  
**Not claimed:** verified novel algorithm, robust recursive feasibility, or paper-ready theorem.

ALNS is an **internal solver** for candidate routes and scenario recourse. The scientific object is the **MPC decision rule** over executable first actions.

## 1. Plant and information

Authoritative plant: `FleetSimulator` + independent `validate_log`.  
Online information: `Observation` / `PublicPlanningSnapshot` — no unreleased evaluation customer IDs, locations, or windows.

## 2. State

At decision epoch \(t\):

| Component | Meaning |
|-----------|---------|
| Vehicle state | Node/position, SOC, load, activity, locked destination, onboard freight, anchor |
| Request lifecycle | hidden / announced / accepted / deferred / rejected / in_service / completed / accepted_unfulfilled |
| Commitments | Previously **accepted** customers not yet completed — hard obligations |
| Time | Global plant clock |

## 3. Controls (first-stage executable actions)

Candidate action \(a \in \mathcal{A}_t\) may include:

- Accept / reject / defer each **currently announced** optional request  
- Physically executable next motions: service a customer, travel to charger and charge, wait, reload/return as supported by the plant  
- Route suffixes are **plans**; only the **first executable plant action** is committed until the next event

Actions that the plant cannot apply (wrong lock, phantom customer, syn_* forecast ID in a real dispatch) are illegal.

## 4. Prediction horizon and uncertainty

- Prediction horizon \(H\): forward window for **sampled future announcements** and recourse planning.  
- Exogenous uncertainty (initial scope): **future customer announcements** (and their windows/locations via a train-fitted anonymous model).  
- **Out of scope for now:** robust energy disturbances, travel-time ambiguity sets — do not silently claim them.

Horizon-based deferral of already-announced ready times (current B0 behavior) is **not** sufficient to call the controller stochastic MPC.

## 5. Hard constraints (nominal)

- Battery, payload, time windows (service start), charger windows  
- Noninterruptible travel / service / charge  
- Depot return accounting per plant rules  
- **Commitment coverage:** every accepted obligation has a validated nominal continuation (B1-style) before new accepts/dispatches  
- Forecast/synthetic customers exist only in planning clones — never in plant acceptance records

## 6. Nonanticipativity

\[
a_t \text{ identical across scenarios};\quad
\text{scenario-specific decisions only after information in }\omega\text{ is revealed.}
\]

Future scenario requests cannot be accepted or served before their simulated release time.

## 7. Objective (working form)

\[
a_t^\star=\arg\max_{a\in\mathcal{A}_t^{\mathrm{safe}}}
\Big[
r_t(a)+\frac{1}{K}\sum_{k=1}^{K} V_H^\pi(s_t,a,\omega_k)-\lambda C_t(a)
\Big]
\]

| Symbol | Meaning |
|--------|---------|
| \(\mathcal{A}_t^{\mathrm{safe}}\) | Candidates with validated nominal continuation for **existing** commitments |
| \(r_t(a)\) | Immediate service / admission value |
| \(\omega_k\) | Sampled future-demand scenario from **train-only** forecast |
| \(V_H^\pi\) | Causal recourse value under policy \(\pi\) over horizon \(H\) |
| \(C_t(a)\) | Distance / energy / charge cost |

Previously accepted commitments are hard. Unreleased futures are optional opportunities.

## 8. Safety assumptions and what remains unproved

**Assumed / engineered (nominal):**

- Matched plant dynamics equal the validator’s nominal physics  
- Executing the first step of a revalidated continuation and retaining a feasible remainder preserves nominal commitment coverage **under deterministic matched dynamics** (to be stated as a conditional lemma only after event/lock contracts are checked)

**Unproved / not claimed:**

- Robust recursive feasibility under disturbance  
- Finite-deadline anytime feasibility theorems beyond cooperative budgets  
- That adaptive computation allocation is theoretically optimal  
- Novelty vs Jiang/Sivagnanam/Dan/He/anytime-feasible MPC without empirical + conceptual differentiation

## 9. Baselines the formulation must beat (or trade off against)

1. Reactive B0 / B1 / M1 (forecast-blind)  
2. **Standard stochastic rollout** using the **same** candidate first-action set, forecast, and compute budget  
3. Insertion MPC  

If (2) matches the proposed rule on first actions and closed-loop metrics, the project is **REVISE/NO-GO** for novelty (Gate 3C lesson).
