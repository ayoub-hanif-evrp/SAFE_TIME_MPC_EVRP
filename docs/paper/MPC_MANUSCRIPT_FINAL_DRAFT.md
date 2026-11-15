# Certificate-Aware Economic MPC for Dynamic EV Routing with Irreversible Acceptances

**Manuscript draft for internal publication decision**  
**Assessment: `INCREMENTAL_RESULT` (not submission-ready as a distinct top-tier contribution)**

## Abstract

Dynamic electric vehicle routing with time windows and battery limits forces controllers to accept or reject customers under partial information. Once accepted, a customer is an irrevocable obligation under our plant rules. We implement Certificate-Carrying Economic MPC (CC-E-MPC): candidate first actions are admitted only if a nominal continuation validator covers all pending and newly accepted customers; admitted candidates are ranked by expected causal rollout value under shared forecasts. A persistent continuation certificate is advanced across noninterruptible travel/service/charge events.  

We correct an overstated invariance claim: the implementable property is **conditional certificate validity** at epochs labeled `CERTIFIED_FEASIBLE`, not unconditional preservation whenever a certificate may be absent. Empirically, certificate persistence (shared with a prior M1 controller) shows **no completed-service difference** versus turning the store off when forecast scoring is enabled (9/9 ties). Development results versus reactive B1 are mixed; a one-shot frozen holdout ties B1/M1/stochastic MPC. We conclude the work is an incremental engineering synthesis, not a demonstrated distinct top-tier scientific advance.

## 1. Introduction

Dynamic VRPs with confirmations and dynamic EVRPs with stochastic requests already study promise protection and predictive charging. Our question was whether persistent executable certificates plus economic MPC yield a *new* capability beyond (i) M1-style certificate retention and (ii) standard stochastic lookahead. This draft answers with the implemented evidence.

## 2. Formal plant model (nominal)

- Euclidean arcs; nominal linear energy; independent chargers.  
- Request lifecycle: HIDDEN → ANNOUNCED → {ACCEPTED, DEFERRED, REJECTED} → IN_SERVICE → COMPLETED (or ACCEPTED_UNFULFILLED at unresolved horizon).  
- Noninterruptible locked travel/service/charge.  
- Decisions observe only public fields (`released_open`, `accepted`, `in_service`, …).

**Objective constants (untuned):** service reward 100, accepted-unfulfilled penalty 250, distance penalty 1.

## 3. Algorithm

### 3.1 Certificate

`ContinuationCertificate`: routes, served, anchors, **post-decision accepted set**, assumptions. Stored in `CertificateStore` with `publish` / `advance_or_invalidate`.

### 3.2 CC-E-MPC

1. Advance/revalidate certificate (and M1-style last certified routes).  
2. Generate counterfactual first actions (serve/accept/reject/charge/wait/ALNS/B1).  
3. Hard filter via `validate_continuation` (including newly accepted).  
4. Score with fail-closed causal scenario rollouts.  
5. Select max expected value (**no** scenario-wise regret floor vs B1).  
6. Emit only if independent re-verify succeeds; publish certificate with full post-decision accepted set.  
7. Else fallback; if still uncovered, label `UNKNOWN` with `uncovered_accepted_obligations` — never silent certified claims.

ALNS is an internal optimizer only.

## 4. Proposition (corrected)

**ConditionalCertificateValidity.**  
If the controller emits `CERTIFIED_FEASIBLE` for observation \(o\) and decision \(d\), and independent `validate_continuation(o,d.\mathrm{routes},\mathrm{require\_new}=d.\mathrm{newly\_accepted})` succeeds under nominal physics, then the certified routes cover \(\mathrm{pending}(o)\cup d.\mathrm{newly\_accepted}\).  

**Proof.** Immediate from the emit-path gate and the validator’s coverage semantics (pending ∪ require_new must be ⊆ served ∪ in_service). Publish records `accepted(o) ∪ newly`.  

**Not proved.** Preservation at epochs where status is `UNKNOWN` or the store is empty.  
**Counterexample to the withdrawn unconditional claim.** Prior regression: ~t=73 on `A_low_soc_charge` seed 7 with accepted C4,C5 and no certified continuation.

## 5. Related work (positioning)

- Dynamic VRP with prompt confirmation of advance requests: protects accepted promises while reoptimizing.  
- Dynamic EVRP with stochastic requests: predictive charging / stochastic lookahead.  
- Backup-plan / safety-filter MPC and feasibility certificates in control.  

**Our delta must not be** “we also use lookahead” or “we also keep a backup plan.” After audit, the certificate *object* is largely M1’s; economic selection is largely stochastic MPC’s.

## 6. Experimental protocol

### 6.1 Synthetic closeout (already evaluated)

- Forecasts fit on train cases only.  
- Development: `A_dense_arrivals`, `A_low_soc_charge`, `B_easy_dynamic` × seeds `{3,7,11}`.  
- Factorial ablation: certificate × forecast.  
- Freeze settings; evaluate holdout `B_adversarial_overaccept` **once** (not reused as fresh validation).  
- Replay-invalid episodes excluded from superiority claims.

### 6.2 Schneider-derived dynamic EVRPTW

Static Schneider–Stenger–Goeke / Goeke E-VRPTW files (DOI 10.17632/h3mrm5dhxw.1) supply geometry, windows, chargers and energy parameters. Controllers never observe hidden customers. Seed semantics separate `environment_seed` (releases) from `policy_seed` (controller RNG). Controllers and objective weights are **unchanged**.

- **Protocol v1** (frozen): clamped announcements; results in `SCHNEIDER_DYNAMIC_RESULTS.json`. Later diagnosed as confounded by zero-duration arc stalls, forecast μ misspecification, and fleet-cap artifacts.  
- **Protocol v2** (active for new work): no announcement clamp (late requests classified); explicit fleet cap metadata; train-calibrated announcement μ. See `DYNAMIC_SCHNEIDER_PROTOCOL_V2.md` and `DATASET_SELECTION_DECISION.md`.

## 7. Results

### Certificate accounting

Post-fix audit: 0 certified-verify failures; 0 publish accepted mismatches; replay ok.

### Ablation (completed customers, 9 valid cells)

| Contrast | Equal | CCE better | CCE worse | Mean Δ |
|----------|------:|-----------:|----------:|-------:|
| Cert on vs off (forecast on) | **9** | 0 | 0 | **0.0** |
| vs M1 | 6 | 1 | 2 | −0.78 |
| vs stochastic MPC | 6 | 1 | 2 | −0.56 |
| vs B1 | 6 | 1 | 2 | −0.56 |

### Development / holdout (synthetic)

- Dev vs B1: 1 win / 2 losses (mean completed Δ −0.56).  
- Holdout: all controllers complete 2 with 0 AU on seeds 3/7/11 (ties).

### Schneider-derived dynamic EVRPTW (36 small instances × 5 environment seeds, medium dynamicity)

See `docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json`. Controllers unchanged.

- High computational/control failure rates for forecast-using methods under the frozen ALNS budget (stochastic MPC 68/180; CC-E-MPC 63/180; B1 10/180), mainly decision-loop stalls.  
- On **paired** cells where both CC-E-MPC and B1 finished (n=112): 49 better / 31 worse / 32 tie; mean completed Δ ≈ +0.60 with CI half-width that includes zero.  
- Unconditional mean completed counts are not comparable across controllers with unequal crash rates.  
- This broader workload **does not** convert the study into a demonstrated predictive superiority claim; it strengthens external validity of the evaluation while leaving the scientific label at **`INCREMENTAL_RESULT`**.

### Oracle honesty

Restricted `{serve,charge}` Case-A: live charge selection (~122 vs 88). Unrestricted EV may prefer wait.

## 8. Limitations

Synthetic suites remain useful for oracles but are insufficient alone; Schneider-derived dynamic episodes improve credibility but still use nominal Euclidean physics and a fixed compute budget that induces frequent stalls for lookahead controllers; certificate persistence remains empirically weak for service counts when forecast scoring is on; literature already covers promise protection and EV lookahead.

## 9. Conclusion

CC-E-MPC is a coherent implementation combining M1-like certificates with economic first-action selection. After integrity closeout and Schneider-derived dynamic evaluation, the **publishable scientific advance remains incremental**: a corrected conditional certificate proposition and a reproducible mixed/unstable empirical record — not a top-tier distinct method claim.
