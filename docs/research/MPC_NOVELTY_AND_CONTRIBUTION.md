# MPC novelty and contribution assessment

**Working title:** Commitment-Safe Stochastic Model Predictive Control for Dynamic Electric Vehicle Routing with Time Windows  
**Implementation SHA (this milestone):** see git `HEAD` after CSS-MPC gates 1–4 + development eval.  
**Approximation class:** restricted candidate-set stochastic MPC with scenario-dependent B1 recourse — **not** an exact extensive-form solve.

---

## 1. What is now technically in place

1. **Transactional commitment emission** — speculative accepts cannot enter `Decision` or the certificate store without independent Validate (Gate 1).
2. **Distinct horizon-end terminal commitment constraint** — `verify_terminal_commitment` / `project_to_horizon` (Gate 2), not a rename of stage-0 Validate.
3. **Strengthened RF theorem** — certified viable set forward invariance under (N1)–(N8); `CERTIFIED_FEASIBILITY_LOST` is an assumption-failure signal, not an RF-preserving escape (Gate 3).
4. **Honest solver description** — candidate-set MPC + scenario rollout recourse; ALNS as subroutine.

---

## 2. Answers to the six scientific questions

| # | Question | Answer (development evidence) |
|---|---|---|
| 1 | Genuinely MPC beyond ordinary scenario rollouts? | **Partially.** Receding-horizon first-action + shared scenarios + hard terminal filter are MPC-structured, but the optimizer remains a **restricted candidate-set rollout**, not a full stochastic program. |
| 2 | RF stronger than M1 certificate validity? | **Yes, formally:** terminal \(\mathcal{X}_f\) + transactional emit + invariance statement for certified epochs. Still **nominal** only; not robust. |
| 3 | EV-specific charging/energy mechanism useful? | **Weak / mixed.** Charge-candidate ablation: CSS vs no-charge completed Δ=+0.83 (CI includes 0). Infinite-battery replay OK; CSS still not ahead of GN. |
| 4 | Closed-loop gain vs strong MPC baselines? | **No clear win vs greedy-nominal.** Completed Δ=−0.72, CI [−2.87, 1.43]; economic Δ=+156 but CI [−285, 596] includes 0. |
| 5 | Defensible compute budget? | **Improved reporting; still weak.** Warm-start is necessary (Δ=+1.94 vs cold, CI excludes 0). CSS latency ≫ GN; cooperative overruns remain. |
| 6 | Differs from published SMPC / DVRP / commitment routing? | **Incremental package** (EV + irreversible accepts + terminal RF + candidate SMPC). Not a new paradigm. |

---

## 3. Top-tier readiness

**Not ready.** Correctness/theory gates advanced; **empirical competitive advantage vs the strongest baseline failed.** Confirmatory evaluation must remain withheld.

Mechanism of failure (current hypothesis): terminal+scenario scoring burns budget and prefers commitment-safe but myopic/conservative first actions relative to greedy-nominal’s unequal but aggressive coverage heuristic — see `MPC_FAILURE_MECHANISM_AUDIT.md` and development paired tables.
