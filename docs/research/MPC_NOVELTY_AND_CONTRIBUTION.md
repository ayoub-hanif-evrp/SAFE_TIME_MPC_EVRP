# MPC novelty and contribution assessment

**Working title:** Commitment-Safe Stochastic Model Predictive Control for Dynamic Electric Vehicle Routing with Time Windows  
**Status:** Research hypothesis under validation — **not** an established novel contribution.  
**Empirical context (dev, SHA `9570621`):** predictive wrappers lose to greedy-nominal CC-E-MPC; confirmatory withheld.

---

## 1. Candidate contribution (hypothesis)

**Commitment-Safe Stochastic MPC with Recursive Feasibility and Energy-Aware Predictive Optimization** for multi-vehicle dynamic EVRPTW with **irreversible accept/reject**, noninterruptible travel/service/charge, and decision-time computation limits.

The intended scientific object is an **MPC problem formulation and solution method**, not a catalogue of heuristic controllers.

---

## 2. Closely related literature (what is already known)

| Theme | Representative work | Overlap | Gap relative to hypothesis |
|---|---|---|---|
| Prompt irreversible confirmation + reoptimization | Sivagnanam et al., ICCPS 2026 ([arXiv:2603.07422](https://arxiv.org/abs/2603.07422)) | Accept/reject with feasible-plan confirmation; anytime manifests | Not EV energy/charge theory; not stochastic MPC recursive feasibility |
| Anticipatory DVRP / ADP rollout | Ulmer et al., TS 2019 | Offline VFA + online rollout over base rules | Single-vehicle non-EV; not commitment certificates + EV physics |
| Initial routing flexibility for dynamic accepts | Soeffker et al., OR Spectrum 2024 | Preserve capacity for future accepts | ICE/fleet workload features; not battery/charge MPC |
| Stochastic energy EVRP | Spinelli et al., TRC 2025 | Scenario energy + recourse charging | Static/two-stage style; not online irreversible commitments + MPC RF |
| Dynamic stochastic EVRP / safe RL | Basso et al., TRE 2022 | Stochastic requests + energy; safety layer | RL + chance constraints; no MPC RF theorem; no rejection commitments |
| Dynamic EVRP proactive charging | Jiang et al., TS 2026 (abstract) | Lookahead / rollout / DQN; proactive charge | No irrevocable acceptance commitment in abstract; not RF-MPC |
| Safe / recursive-feasibility MPC | Classical constrained MPC literature | Terminal sets, backup controllers | Rarely combined with discrete routing acceptances + EV energy |
| Certificate-carrying routing MPC (this repo) | M1 / ConditionalCertificateValidity | Nominal coverage certificates | Restates epoch-wise validation; **not** a nontrivial recursive-feasibility theorem for stochastic MPC |

Prior repo note: `docs/research/TOP_TIER_NOVELTY_AND_GAP.md` and `docs/literature/PRIOR_ART_AND_RESEARCH_GAP.md`.

---

## 3. What would need to be true for a top-tier paper

A serious contribution likely requires **all** of:

1. **Nontrivial recursive commitment-feasibility result** for the specified EV system (assumptions on energy/travel, noninterruptible locks, terminal set / backup policy), not merely “validator returned OK at time \(t\)”.
2. **Distinct tractable stochastic MPC formulation or solution technique** (nonanticipative scenarios, terminal commitment constraint, warm-started solver) that is recognizably MPC.
3. **Demonstrable gains attributable to EV-specific predictive decisions** (charging / SoC positioning), via controlled ablations with valid replay — not demand forecasting alone.
4. **Honest computation evidence** (latency percentiles, quality vs budget) without claiming hard real-time guarantees the solver cannot meet.

**Combining** certificates + forecasts + ALNS is **not** novelty by itself.

---

## 4. What this repository has demonstrated so far

| Claim | Demonstrated? |
|---|---|
| Event-triggered EVRPTW-D simulator + independent replay | Yes |
| Certificate-carrying reactive MPC (M1) | Yes (empirical) |
| ConditionalCertificateValidity (epoch-wise) | Yes (limited theorem) |
| Causal forecast scoring without leakage | Largely yes (tests + contract) |
| Predictive / BAP / DF-BAP beats greedy-nominal | **No** (dev gate failed) |
| EV-specific predictive mechanism | **No** (infinite-battery ablation invalid: `replay:travel_energy`) |
| Recursive feasibility for stochastic MPC | **Not yet** (this milestone drafts the proof under assumptions) |

---

## 5. Precise niche still open (if executed)

Stochastic **receding-horizon** control for **electric** fleets where:

- acceptances are **irreversible obligations**,
- a **terminal commitment set** (or certified backup policy) yields a **conditional recursive feasibility** theorem under stated plant assumptions,
- predictive **charging and positioning** are first-class decisions interacting with request scenarios,
- and the method remains computationally practical with incumbent-first anytime fallback.

Closest competitors cover pieces (Sivagnanam confirmation; Ulmer rollout; Spinelli energy scenarios; classical RF-MPC) but not this package under EVRPTW-D commitments. That **package gap is a hypothesis**, not a novelty medal.

---

## 6. Novelty language policy

Allowed: comparative, conditional, “we prove under assumptions…”, “on this protocol…”.  
Forbidden until theorem + valid EV ablation + development gate + confirmatory: “first”, “novel paradigm”, “solves dynamic EVRP”.

Negative historical results (predictive loss to greedy-nominal; invalid infinite-battery cell) remain part of the manuscript record.
