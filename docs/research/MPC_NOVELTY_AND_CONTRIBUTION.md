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
| 3 | EV-specific charging/energy mechanism useful? | **Not demonstrated.** Infinite-battery (rebuilt arcs, 0 replay failures) still has CSS behind GN (7.0 vs 9.3 completed on n=3). |
| 4 | Closed-loop gain vs strong MPC baselines? | **No vs greedy-nominal.** Completed mean 4.5 vs GN 5.5 (paired Δ=−1.0, 7/8/3). Beats B1/M1 on completed tally, which is insufficient. |
| 5 | Defensible compute budget? | **Weak.** CSS deadline overruns sum=273 vs GN=13 at 0.35s cooperative wall. Not hard real-time. |
| 6 | Differs from published SMPC / DVRP / commitment routing? | **Incremental package** (EV + irreversible accepts + terminal RF + candidate SMPC). Not a new paradigm; literature already covers pieces (Sivagnanam, Ulmer, Spinelli, classical RF-MPC). |

---

## 3. Top-tier readiness

**Not ready.** Correctness/theory gates advanced; **empirical competitive advantage vs the strongest baseline failed.** Confirmatory evaluation must remain withheld.

Mechanism of failure (current hypothesis): terminal+scenario scoring burns budget and prefers commitment-safe but myopic/conservative first actions relative to greedy-nominal’s unequal but aggressive coverage heuristic — see `MPC_FAILURE_MECHANISM_AUDIT.md` and development paired tables.
