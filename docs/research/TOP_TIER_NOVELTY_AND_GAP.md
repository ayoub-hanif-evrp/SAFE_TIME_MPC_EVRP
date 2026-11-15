# Top-tier novelty and research gap (Stage 0)

**Repo SHA at analysis:** `ab45add`  
**Hypothesis under test (not a novelty claim):**  
*Commitment-Constrained, Budgeted Policy Improvement with Decision-Focused Value Estimation* for online electric fleets with irreversible acceptances.

**No unsupported “first” claims.** Closely related work already covers substantial parts of the hypothesis.

---

## 1. Comparator papers (problem / algorithm / guarantee / experiments)

| Paper | Problem | Algorithm | Guarantees | Experiments |
| --- | --- | --- | --- | --- |
| **Sivagnanam et al., ICCPS 2026** ([arXiv:2603.07422](https://arxiv.org/abs/2603.07422)) | DVRP with **prompt accept/reject confirmation** + continual reoptimization of manifests; irreversible accepts | Quick insertion for confirmation + anytime manifest search; RL-trained non-myopic objective | Feasible-plan confirmation for accepts; **not** EV energy/charge theory | Real US microtransit data; confirmation latency vs service rate |
| **Ulmer et al., Transportation Science 2019** ([doi:10.1287/trsc.2017.0767](https://doi.org/10.1287/trsc.2017.0767)) | Single-vehicle DVRP with stochastic requests | Offline VFA + online rollout (hybrid ADP); policy-improvement over deterministic base rules | Rollout improvement guarantee **when** base is deterministic decision rule (under their MDP) | Synthetic spatial/temporal request settings |
| **Soeffker et al., OR Spectrum 2024** ([doi:10.1007/s00291-024-00747-1](https://doi.org/10.1007/s00291-024-00747-1)) | Fleet DVRP: serve all initial customers + maximize dynamic accepts | Efficiency–flexibility trade-off in initial routing; VFA with workload-balance features | Empirical; feasibility of initial obligations | Same-day style instances; ~10.75% gain from balancing |
| **Laroche et al., ICML 2019 (SPIBB)** ([PMLR](https://proceedings.mlr.press/v97/laroche19a.html)) | Batch RL safe policy improvement vs baseline | Bootstrap to baseline in poorly counted (s,a); Π_b-SPIBB | High-probability SPI vs baseline under batch MDP assumptions | Gridworld / random MDPs / SPIBB-DQN |
| **Spinelli et al., TRC 2025** ([doi:10.1016/j.trc.2025.105480](https://doi.org/10.1016/j.trc.2025.105480)) | EVRP with **stochastic energy**; threshold charging recourse | Two-stage stochastic MISOCP + ILS/set-partitioning | Recourse-defined feasibility under energy scenarios | Up to ~80 customers; scenario reduction |

**Adjacent themes (not exhaustive):** time-dependent EVRP, nonlinear charging curves, learning-guided ALNS, safe MPC with certificates. These further shrink any claim that “MPC + certificates + forecasts” alone is novel.

---

## 2. Where this repository currently sits

| Element | Status vs literature |
| --- | --- |
| Irreversible acceptance + feasible continuation | Overlaps Sivagnanam prompt confirmation and Soeffker “serve all initial” |
| Baseline-anchored override | Conceptual cousin of SPIBB / Ulmer base+rollout — **but** current BAP lacked matched budget and store sync (Stage 1 defect) |
| Offline VFA + online rollout | Ulmer already defines the hybrid ADP pattern |
| EV energy uncertainty | Spinelli addresses stochastic consumption; our plant is mostly nominal linear energy |
| Battery/charge flexibility as mechanism | Soeffker-style workload flexibility is ICE/fleet; EV-specific mechanism **not yet demonstrated** (Stage 4 gate) |
| Existing `ConditionalCertificateValidity` | Close to restating M1 `CertificateStore` validation — **not** a distinctive theorem by itself |

---

## 3. Remaining research niche (hypothesis, not claim)

A **plausible** distinguishable contribution, if executed rigorously, would combine:

1. **Electric-specific commitment viability** under event-triggered decisions, noninterruptible travel/charge, and a **computable inner approximation** of the viable set (beyond “validator returned OK”).
2. **Budgeted online SPI-style improvement** over a **matched** strong commitment-preserving incumbent (greedy-nominal CC-E), with explicit sampling / misspecification / selection-bias caveats (SPIBB is batch MDP; Ulmer is single-vehicle non-EV).
3. **Decision-focused advantage estimation** \(A(o,a)\) rather than absolute forecast-customer scoring, with independent confirmation that EV constraints (not only request anticipation) drive gains.
4. **Measured cooperative decision-time budgets** with anytime incumbent fallback — related to Sivagnanam anytime manifests, but here for EV commitment + economic override.

If (1)–(3) collapse to “Ulmer rollout + M1 certificate + SPIBB-like keep baseline,” the paper is **not** top-tier ready without a sharper theorem or a large reproducible empirical win on EV-specific factors.

---

## 4. Central research question (adopted)

Can an online electric-fleet controller improve expected service and economic value over a **strong commitment-preserving incumbent** while:

- respecting irreversible accepted-customer obligations,
- handling uncertain online requests,
- explicitly valuing battery and charging flexibility,
- and operating within a **measured** decision-time budget?

---

## 5. Stage-0 gate decision

| Criterion | Decision |
| --- | --- |
| Entire proposed mechanism already published as a package? | **No** — but every major *ingredient* has a close ancestor |
| Proceed to Stages 2–5 after Stage 1? | **Yes, conditionally** — only as *commitment-constrained budgeted SPI for EV fleets*, with EV ablation as a hard requirement |
| Novelty language allowed? | Comparative / incremental only; no “first” / “novel paradigm” until theorem + confirmatory results exist |

**Immediate priority:** Stage 1 validity (matched incumbent, store sync, information contract, honest calibration). Do **not** claim readiness.
