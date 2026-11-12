# Project handoff — SAFE_TIME_MPC_EVRP (for a new chat)

**Purpose of this file:** paste or attach this into a new ChatGPT / Cursor chat so work continues without losing context.  
**Last updated:** 2026-11-12  
**Active branch:** `research/commitment-safe-predictive-mpc`  
**Remote:** `https://github.com/ayoub-hanif-evrp/SAFE_TIME_MPC_EVRP.git`  
**Repo path (local):** `SAFE_TIME_MPC_EVRP`

### Latest milestone — Phase 3D (REVISE)

MPC-central track (`docs/mpc_central/`): repaired plant distance + B1 scenario recourse + non-renormalizing expectation; added `CommitmentSafePredictiveMpc` and a small closed-loop pilot. **Verdict REVISE** — predictive MPC not yet better than B1 on development cases; Phase 3C adaptive wins remain order-fragile. See `PHASE3D_VALIDITY.md`, `PHASE3D_CLOSED_LOOP_RESULTS.md`, `phase3d_results.json`. Do not treat adaptive top-two allocation as the paper contribution.

---

## 1. One-sentence project goal

Build **Computation-Aware, Commitment-Safe Model Predictive Control for Dynamic Electric Vehicle Routing (D-EVRP)**: high-quality accept/route/charge decisions under dynamic requests, battery/charging physics, and limited optimize time, while protecting previously accepted customer commitments under an explicitly stated (currently nominal) feasibility model.

---

## 2. What this PhD cycle is *not*

Earlier tracks were explored and largely **quarantined / negative**:

- Dual-control toys, DRUB/REUB/OTUB-style bounds, invented VoI bounds  
- Quarantined TEI, A/C/S trees, degenerate 8×9.75 suites  
- Claiming novelty from Part 2 rectangle certificates alone  
- Manufacturing “wins” by weak baselines or fake incremental evaluation  

**Current main trajectory (frozen as the research path):**

> Authoritative D-EVRP plant → strong reactive ALNS–MPC (B0) → full-validation safe MPC (B1) → certificate-carrying incremental M1 → matched fixed-budget experiments → honest go / no-go for a paper claim.

Do **not** restart dual-control toys unless the user explicitly asks. Stay on D-EVRP → MPC → commitment safety.

---

## 3. Repository layers (mental model)

| Layer | What it is |
|-------|------------|
| **Plant** | `FleetSimulator` + independent `validate_log` replay — the ground truth |
| **Information boundary** | `PublicPlanningSnapshot` — planner must not see unreleased customers |
| **Baseline MPC** | Event-triggered insertion (`EventTriggeredMPC`) — Part 1 style |
| **B0** | `ReactiveAlnsMpc` — ALNS search under cooperative time budget + request-rescue |
| **B1** | `FullValidationAlnsMpc` — same ALNS + independent nominal continuation validation before accept/dispatch |
| **M1** | `CertificateCarryingAlnsMpc` — B1-style safety + incremental route-resource eval + event-aware certificate store |
| **Evidence** | Matched Insertion / B0 / B1 / M1(+ablations) JSON under `docs/commitment_safe_mpc/` |

Package root: `src/safe_time_evrp/`  
Active research package: `src/safe_time_evrp/commitment_safe_mpc/`  
Docs for this track: `docs/commitment_safe_mpc/`

The top-level `README.md` still describes Part 1 / Part 2 foundations. The **current research narrative** lives in `docs/commitment_safe_mpc/RESEARCH_SCOPE.md`, not only in the root README.

---

## 4. Controllers and scientific roles

### Insertion (baseline)
Deterministic event-triggered insertion MPC. Always included in matched studies for fairness.

### B0 — Reactive ALNS–MPC (`alns_mpc.py`)
- Same plant and public snapshot as everyone else  
- ALNS destroy/repair under `time_limit_seconds`  
- **Request-rescue:** recovers customers the constructor misses (fixture: packing case `{A,B}` → `{A,B,C}`)  
- Hardened: genuine regret-k, arc-preserving snapshot, sequence-consistent decode, `executed_distance` (not fake planned distance), safe `UNKNOWN` failure  

### B1 — Full-validation safe ALNS–MPC (`full_validation_mpc.py`)
- Wraps B0’s ALNS engine  
- Every acceptance/dispatch requires `validate_continuation` witness  
- **Nominal** physics only — **not** robust recursive feasibility against unknown disturbances  

### M1 — Certificate-carrying ALNS–MPC (`m1_mpc.py`)
Intended contribution candidate:

1. **Inner-loop incremental evaluation** (`EvalMode.INCREMENTAL_EVALUATION` in `route_resource_profile.py`): freight-aware prefix reuse + suffix `propagate_from_state` without calling full `evaluate_route` on every candidate  
2. **Cross-event certificates** (`certificate_store.py`): retain / advance certificates across MPC events by truncating completed services and updating anchors (not “exact identical timestamps”)  
3. Same outer validation contracts as B1  

**Ablations:** `m1_no_reuse`, `m1_full_eval`, `m1_both_off`.

---

## 5. What was completed (chronological)

### Phase A — diagnostics / CI hygiene
Policy-class alignment D1–D4; scenario diagnostics; green CI discipline.

### Phase B — authoritative plant
`FleetSimulator` + `validate_log` as sole ground truth; Phase B demo criteria met (multi-EV, dynamic release, charging, multi-replan, commitments fulfilled, replay OK).

### Phase C — B0
Reactive ALNS–MPC + public snapshot + matched vs insertion; then **hardening** after audit (no circular imports, real metrics, no fake regret/decode).

### Phase D — B1 + rescue
Full-validation MPC; request-rescue ALNS; revalidation / bottleneck profiling (`compute_bottleneck_profile.json`). Finding: **inner route evaluation dominates** outer B1 validation time.

### Phase E — M1 + urgent correctness repair
First M1 pass had serious defects; repaired:

1. False certificates (onboard / locked destination wrongly covering commitments)  
2. Freight-aware prefix theorem (depot manifest mismatch blocks false reuse)  
3. **Real** incremental hot path (`evaluate_route_calls ≈ 0` in ALNS hot path; counters for reused/recomputed visits)  
4. Event advancement of certificates  
5. Episode-aggregated profiles from **all** decision audits  

### Phase F / Priority 7 — fixed-budget frontier (DONE)
- Suite: `build_frontier_suite()` — 10/20/30/50 customers, tight SOC, two chargers, dynamic releases + rescue pack  
- Runner: `budget_frontier.py`  
- Artifact: `docs/commitment_safe_mpc/budget_frontier.json` (**285** raw runs)  
- Budgets `{0.05, 0.15, 0.40}` s; seeds `{3,7,11}`; controllers Insertion/B0/B1/M1(+ablations); iterations capped at 80 so the deadline binds  
- Smoke tests: `tests/test_budget_frontier.py`

**Headline vs B1 (15 case×budget cells):**

| Result | Count |
|--------|-------|
| M1 faster (mean optimize_seconds) | **13 / 15** |
| M1 higher mean completed customers | **2 / 15** |

Interpretation written into docs without marketing: **incremental eval is genuine and usually cheaper; saved compute does not reliably buy better service on this suite.**

---

## 6. Current scientific verdict

**Paper claim: NOT YET.**

- Correctness of M1’s incremental / certificate machinery: **substantially fixed and tested**  
- Compute savings vs B1: **supported on development evidence**  
- Better commitment-safe decisions under fixed budget: **not established** (often tied; sometimes M1 worse on completed)  
- Novelty vs standard resource-prefix / labeling literature: **not claimed**  
- Robust commitment safety under disturbance: **not claimed** (nominal only)

Authoritative write-ups:

- `docs/commitment_safe_mpc/SCIENTIFIC_VERDICT.md`  
- `docs/commitment_safe_mpc/COMPUTATION_SERVICE_FRONTIER.md`  
- `docs/commitment_safe_mpc/PUBLICATION_READINESS.md`

---

## 7. Key source files

```
src/safe_time_evrp/commitment_safe_mpc/
  plant.py                     # plant bridge / lazy imports
  public_snapshot.py           # information boundary
  alns_mpc.py                  # B0 ReactiveAlnsMpc + rescue
  full_validation_mpc.py       # B1
  m1_mpc.py                    # M1
  continuation_validate.py     # independent continuation witness
  route_resource_profile.py    # EvalMode, profiles, incremental eval
  certificate_store.py         # event-aware certificate retention
  baseline_suite.py            # toy + scaled + frontier suites
  baseline_compare.py          # matched Insertion/B0/B1/M1 study
  compute_profile.py           # bottleneck / work counters
  budget_frontier.py           # Priority-7 frontier runner
  phase_b_demo.py              # Phase B demo instance

tests/
  test_commitment_safe_*.py
  test_m1_correctness_repair.py   # false-cert / freight regressions
  test_budget_frontier.py
```

---

## 8. Key commands

```bash
# Env
pip install -e ".[dev]"

# Tests (commitment-safe focus)
python -m pytest tests/test_budget_frontier.py tests/test_commitment_safe_m1.py tests/test_m1_correctness_repair.py -q

# Full suite (when changing broadly)
python -m pytest -q

# Matched baseline / ablations
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --m1
python -m safe_time_evrp.commitment_safe_mpc.compute_profile

# Priority-7 frontier (long: ~30 min full; use --quick for smoke)
python -m safe_time_evrp.commitment_safe_mpc.budget_frontier
python -m safe_time_evrp.commitment_safe_mpc.budget_frontier --quick
```

---

## 9. Standing research rules (do not violate)

1. **No manufactured wins** — report ties and losses; paper claim stays NOT YET until evidence says otherwise.  
2. **Plant is authority** — every episode must `validate_log`; controllers do not redefine physics.  
3. **Public information only** — no peeking at unreleased demand.  
4. **Matched comparisons** — same instances, releases, horizons, seeds, budgets when claiming A beats B.  
5. **Nominal ≠ robust** — do not claim recursive feasibility under unknown disturbances.  
6. **Fake incremental is forbidden** — if claiming incremental eval, `evaluate_route_calls` in the ALNS hot path must stay near zero and counters must be real.  
7. **Commitments covered only by served ∪ IN_SERVICE** — not by onboard/locked destination alone.  
8. Stay on **commitment-safe D-EVRP MPC**; do not pivot back to dual-control toys without explicit user request.

---

## 10. Remaining scientific blocker (what a new chat should attack next)

Saved ALNS evaluations are real, but they **do not systematically change the executable decision set** under fixed budgets on the current frontier suite.

Next options (research, not busywork):

1. **Find a regime** where extra ALNS iterations from saved evals systematically improve accept/charge/service (tighter deadlines, harder charging, larger dynamic release pressure).  
2. **Change the mechanism**, not only the inner evaluator — e.g. certificate-guided destroy/repair, anytime incumbent that privileges commitment-critical customers, budget allocation across vehicles/events.  
3. **Larger multi-seed / holdout campaign** only after (1) or (2) shows a coherent signal — do not burn Schneider/Amazon-scale runs to reconfirm “faster but same service.”  
4. Clarify **novelty** relative to Vidal / Erdelić / labeling / resource-extension literature; event-aware MPC certificate advancement is the candidate distinction, not “we reuse prefixes.”

---

## 11. How the user was working with assistants

- Long Cursor agent sessions implemented B0 → B1 → rescue → M1 → M1 repair → Priority 7.  
- Parallel ChatGPT planning chats defined priorities and scientific gates; when a ChatGPT thread hits context limits, **this handoff file** is the bridge.  
- User instruction pattern: “complete what should be completed,” stay honest, push when the milestone is done.  
- Commits are on `research/decision-relevant-dual-mpc`; do not amend history or force-push unless asked.

Recent milestone commits (newest first):

```
6e8187c Complete Priority-7 fixed-budget frontier study without claiming service wins.
30bbf4f Regenerate honest M1 ablations with episode-aggregated work counters.
5e034c0 Implement real suffix propagation and physical-event certificate advancement.
ab4024c Fix false commitment certificates and freight-aware prefix reuse conditions.
80fe566 Record M1 ablations and an honest publication-readiness verdict.
243613d Add event-aware certificate-carrying M1 on the shared ALNS engine.
```

---

## 12. Suggested prompt to start the next chat

Copy-paste:

> Read `docs/commitment_safe_mpc/PROJECT_HANDOFF_FOR_NEW_CHAT.md` and `SCIENTIFIC_VERDICT.md`. We are on branch `research/decision-relevant-dual-mpc` working on Computation-Aware Commitment-Safe MPC for D-EVRP. Priority 7 frontier is done: M1 is faster than B1 but does not win service. Paper claim is NOT YET. Help me decide and implement the next scientific step (regime search vs new mechanism), without manufactured wins and without restarting dual-control toys.

---

## 13. Companion docs index

| File | Role |
|------|------|
| `RESEARCH_SCOPE.md` | Objective + milestone table |
| `PHYSICAL_CONTRACT.md` | Plant / observation / commitment semantics |
| `BASELINE_COMPARISON.md` | Matched protocol |
| `ALNS_REQUEST_RESCUE.md` | Rescue mechanism |
| `FULL_VALIDATION_MPC.md` | B1 contracts |
| `M1_ALGORITHM.md` | M1 design |
| `INCREMENTAL_RESOURCE_CERTIFICATE.md` / `INCREMENTAL_CERTIFICATE_FORMULATION.md` | Certificate theory notes |
| `INCREMENTAL_PROOF_AND_COUNTEREXAMPLES.md` / `PROOF_AND_COUNTEREXAMPLES.md` | Props + falsifiers |
| `M1_ABLATION_RESULTS.md` | Ablation reading |
| `COMPUTATION_SERVICE_FRONTIER.md` | Priority-7 numbers |
| `EXPERIMENTAL_EVIDENCE.md` | Artifact table |
| `SCIENTIFIC_VERDICT.md` | Go / no-go |
| `PUBLICATION_READINESS.md` | What is / isn’t paper-ready |
| `budget_frontier.json` | Raw + summary frontier results |
