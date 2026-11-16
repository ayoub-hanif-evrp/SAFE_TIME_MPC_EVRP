# Top-tier readiness — Commitment-Safe Stochastic MPC

**Verdict:** `not_ready_corrected_development_gate_failed`

**Protocol:** `mpc_corrected_development_v1`  
**Stopping rule:** no confirmatory campaign.

## Gates

| Gate | Status |
|---|---|
| 1 Transactional acceptance safety | **PASS** |
| 2 Horizon-end terminal commitment (freeze + residuals) | **PASS** (pytest) |
| 3 RF claim ↔ code | **PASS** as **certified-emission soundness** (RF withdrawn) |
| 4 Formulation honesty | **PASS** |
| 5 EV energy / infinite-battery replay | **PASS** (rebuilt arcs; n=3 stems) |
| 6 Corrected ablations + decision-level latency + clustered CIs | **PASS** (reporting) |
| 7 Reliable economic advantage vs greedy-nominal | **FAIL** |
| 8 Confirmatory | **WITHHELD** |

## Corrected development snapshot

Stems (all `stratified_split_small()["development"]`):  
`c103C5`, `r105C5`, `rc108C5`, `c104C10`, `r103C10`, `rc108C10`, `c106C15`, `r105C15`, `rc108C15`  
(n=18 episodes = 9×2; failures included)

| Controller | Completed | AU | Economic | Decide p50 / p99 | Overruns | Loss events |
|---|---:|---:|---:|---:|---:|---:|
| B1 | 3.06 | 3.56 | −727 | 0.002 / 0.385 | 47 | 0 |
| M1 | 4.72 | 1.56 | −114 | 0.001 / 0.397 | 29 | 0 |
| Greedy-nominal | **5.11** | 1.00 | 42 | 0.006 / 0.324 | 10 | 0 |
| Stochastic CCE | 4.39 | 1.83 | −194 | 0.043 / 0.551 | 192 | 0 |
| **CSS-MPC** | 4.72 | **0.72** | **115** | 0.055 / 0.574 | **233** | **147** |
| CSS no-forecast | 4.28 | 0.50 | 118 | 0.035 / 0.489 | 163 | 112 |

Primary metric: `100×completed − 250×AU − distance`.

Clustered paired CSS vs GN (stem means):

- Economic Δ mean **+72.6**, median **−30.6**, tally **4/5/0**, 95% CI **[−526, +672]** (includes 0).
- Completed Δ mean **−0.39**, CI includes 0.
- AU Δ mean **−0.28**, CI includes 0.

Heavy tails: `c106C15` (+1776 econ) vs `r103C10` (−880). Mean without reliable stem majority.

## Ablation / mechanism (corrected)

| Question | Result |
|---|---|
| Forecast margin | CSS ≈ no-forecast economically (Δ≈−3; CI includes 0); forecast no longer clearly harmful after margin rule |
| Terminal on | Lower AU (0.72 vs 1.56 no-terminal); economic better with terminal |
| Anticipatory charge off | Charge time 186→91; completed drops to 3.56 — predictive charge still used by CSS |
| Warm init (backup kept) | Large economic loss without warm init (−474 vs +115) |
| Warm+backup removed | Separately worse; not an isolated warm-start claim |
| Infinite battery (n=3) | Replay OK; CSS ≥ GN on these three stems — **too small** for EV-specific claim |

## Runtime

Decision-level (pooled decide seconds, not episode-mean percentiles): CSS frac_over_budget **23.3%**, p99 **0.57s** under cooperative 0.35s (pre-checkpoint campaign). Hard ALNS preemption unavailable.

Post-`cbbdd36` completion: checkpointed scoring, commit-time reserve, first-action dedup, top-K scenario expansion, terminal cache — see `MPC_RUNTIME_PROFILE.md`. Cooperative-budget hits reported separately from deadline overruns. Does **not** reopen the failed economic development gate.

## Novelty / contribution assessment (Phase 9)

Supported engineering advances: transactional commit, horizon freeze with residual obligations, certified-emission soundness, corrected evaluation protocol.

**Not yet a top-tier MPC contribution:** no proved recursive feasibility; no reliable economic or service gain over greedy-nominal under equal budget; forecast value not demonstrated; decision-time overruns remain severe. Warm-start/validation alone is insufficient novelty.

Historical negative evidence retained in `MPC_DEVELOPMENT_COMPARISON.*` and prior archives.

## Bottom line

Corrected science and reporting are in place. Credible superiority is **not** demonstrated. Stop per protocol; do not inspect or tune on test stems.
