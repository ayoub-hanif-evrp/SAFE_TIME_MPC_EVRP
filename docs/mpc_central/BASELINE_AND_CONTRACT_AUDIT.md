# Baseline and contract audit (Phase 0)

**Branch:** `research/commitment-safe-predictive-mpc` (from `research/decision-relevant-dual-mpc` @ `6e8187c`)  
**Date:** 2026-11-11  
**Scope:** Inspect, repair, preserve — no Phase-4 controller yet.

## Git / CI

| Item | Status |
|------|--------|
| Working tree at audit start | Clean research tip + untracked handoff MD |
| New branch | `research/commitment-safe-predictive-mpc` |
| Ruff B007 in `budget_frontier.py` | **Fixed** (`_case`, `_seed` in planning loop) |
| Historical artifacts | Preserved (`docs/commitment_safe_mpc/*`, Gate 3C–4 decisions) |

## What B0/B1/M1 actually are

| Controller | Predictive? | Stochastic futures? | Role |
|------------|-------------|---------------------|------|
| Insertion / B0 `ReactiveAlnsMpc` | Receding-horizon **reoptimization** of *already released* customers | No | Strong reactive routing + accept/reject |
| B1 `FullValidationAlnsMpc` | Same + independent nominal continuation gate | No | Commitment-safe reactive MPC |
| M1 `CertificateCarryingAlnsMpc` | Same + incremental eval / certificates | No | Faster B1-class search, not predictive demand MPC |

**Horizon semantics today** (`construct_routes` / public snapshot):

- `PublicPlanningSnapshot` exposes **all currently visible** customers (released/accepted/…); it does **not** use `horizon` to hide announced demand.
- `horizon` only **defers** optional open customers whose `window.ready > now + horizon` (and sets `horizon_extended` for accepted customers with ready beyond H).
- That is **time-window deferral**, not scenario-based stochastic prediction of unreleased announcements.

**Conclusion:** Active B0/B1/M1 are best described as *event-triggered, commitment-aware receding-horizon routing with safety validation*, not mature stochastic predictive MPC.

## `accepted_unfulfilled` vs `replay_ok`

From `budget_frontier.json` (285 runs):

- **31 / 285** episodes have `accepted_unfulfilled_count > 0` (mostly `B_frontier_30` / `B_frontier_50`).
- **All 31** still have `replay_ok=True`.

Contract facts:

1. `validate_log` returns `ok=True` when the **physical event log** is consistent. It **reports** `accepted_unfulfilled` but does **not** treat it as a replay failure (`replay.py`).
2. `FleetSimulator.mark_finished()` maps remaining `ACCEPTED` → `ACCEPTED_UNFULFILLED` at episode end.
3. Episodes can stop because `next_event_time > t_max` even with open accepted work — so some unfulfilled rows are **time-censoring / incomplete service**, others are **true over-acceptance** relative to remaining feasible day.

**Do not equate `replay_ok` with commitment fulfillment.** Frontier `commitment_violations` already counted `accepted_unfulfilled`; Phase-B demo correctly required `accepted_unfulfilled == []`.

**Repair stance for MPC-central:** treat terminal `accepted_unfulfilled` as a first-class reliability metric; separate censored episodes (`t_max` hit with busy fleet) from clear over-accept failures before any safety claim.

## Prior negative gates (do not repackage)

| Gate | Verdict | Lesson |
|------|---------|--------|
| 3C flexibility terminal | **NO-GO** | Same first actions as strong rollout |
| 3F / 4 commitment-cost / UB claims | **NO-GO** / withdrawn | No differentiated mechanism vs ADP/Jiang-style prior art |
| Priority-7 M1 frontier | Compute yes, service dominance **no** | Inner evaluator ≠ better decisions |

## Forecast infrastructure to reuse

`src/safe_time_evrp/mpc3c/forecast.py` already encodes:

- Train-only atoms (`fit_empirical_arrivals`)
- Anonymous `syn_*` scenario customers
- Quarantine of `build_scenarios_for(instance=...)` (eval leak)
- Explicit note that pooled ready gaps are **not** announcement λ̂
- Separate release vs forecast seeds

MPC-central must keep those boundaries (tests added under `tests/test_mpc_central_forecast_safety.py`).

## Phase-0 deliverable checklist

- [x] Branch from research tip without rewriting history  
- [x] CI Ruff B007 repair  
- [x] Horizon = deferral, not stochastic MPC — documented  
- [x] `accepted_unfulfilled` audited — not equal to replay failure  
- [x] Gate 3C–4 negatives preserved as stop signs for recycled mechanisms  
