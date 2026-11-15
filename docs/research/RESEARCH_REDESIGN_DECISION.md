# Research redesign decision (after Stage 0–1)

**Stage 0+1 SHA:** *(filled at commit)*  
**Novelty gate:** Proceed **conditionally** (see `TOP_TIER_NOVELTY_AND_GAP.md`).

## Stage 1 outcomes

| Issue | Finding | Fix |
| --- | --- | --- |
| BAP incumbent budget | Nested CCE used `0.45 ×` wall budget | Matched full budget |
| Certificate store | Separate stores desynced after override | Shared `store`; resync on override |
| Equivalence | Wall-clock ALNS races prevent bit-exact match | `allow_override=False` + `equivalence_mode` (iteration-primary) |
| `c208C15` (inspected) | Pre-fix BAP completed 2 vs GN 15 | Iteration-primary ZO=GN=15; wall BAP≈13 |
| Public \(N\) | Used `len(instance.customer_ids())` implicitly | `Observation.public_customer_count` + contract doc |
| Calibration honesty | 132=132 partly mechanical | Segment MAE + size strata + honesty note |

## Go / no-go for Stages 2–5

| Gate | Status |
| --- | --- |
| Correctness defects fixed + tests | **Pass** (this milestone) |
| Distinct theorem beyond M1 restatement | **Pending** Stage 2 write-up |
| Decision-focused advantage beats hand features on **dev** | **Not started** |
| EV ablation shows EV-specific mechanism | **Not started** |
| Stage 6 confirmatory protocol | **Blocked** until above pass |

**Decision:** Implement Stage 2 formalization and Stage 3 advantage estimator next. Do **not** launch Stage 6. Do not retune on `c208C15`.
