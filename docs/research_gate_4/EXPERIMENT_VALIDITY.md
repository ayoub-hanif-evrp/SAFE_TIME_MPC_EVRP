# Gate 4 — Experimental Validity

## A1 Offline references (corrected)

Gate 3F called `offline_service_upper_bound()` on a constructive insertion plan. A feasible heuristic with \(z_{\mathrm{heur}}\) served customers proves only
\[
z_{\mathrm{heur}}\le z^\star_{\mathrm{offline}},
\]
i.e. a **feasible lower bound**, not an upper bound.

| Label | Meaning | Implementation |
|-------|---------|----------------|
| `FEASIBLE_LOWER_BOUND` | Constructive / validated feasible service count | `constructive_feasible_lower_bound` |
| `CERTIFIED_UPPER_BOUND` | Valid relaxation (cardinality of window-feasible announcements) | `certified_cardinality_upper_bound` |
| `EXACT_OPTIMUM` | Proven inside enumerated single-full-charge-per-gap family | `_enumerate_offline_served` (≤6 customers) |
| `UNKNOWN` | Insufficient evidence | returned when exact skipped / incomplete |

**Withdrawn claim:** controllers attaining the “offline service upper bound” in Gate 3F.

**`a_priori_impossible`:** depot-after-announce travel check removed. Only `max(announce, ready) > due` remains valid without assuming depot departure. Offline vehicles may preposition.

**Commands**
```bash
python -m pytest -q tests/test_gate4_validity.py -k offline
python -c "from safe_time_evrp.mpc3c.offline_reference import heuristic_strictly_below_exact_counterexample as f; print(f())"
```

## A2 Announcement process

Pooled `window.ready` gaps across training instances are **not** request interarrivals. `fit_empirical_arrivals` retains spatial atoms; its `train_interarrival_mean` is labeled `NOT_valid_announcement_interarrival`.

Plant releases use `AnnouncementProcessSpec` with preregistered \(\mu\in\{8,15,25\}\) (`GATE4_DEV_ANNOUNCEMENT_SPECS`), chosen before scoring controllers.

## A3 Strong reactive baseline

`ControllerKind.REACTIVE` plans all currently announced customers with known windows, preserves commitments via the same plant gate, ignores anonymous forecasts. Weak ready-only myopic is labeled `weak_ready_only_myopic`.

## A4 Timing contract

`TimingContract.BLOCKING_WITH_PLANT_ADVANCE`: optimize blocks dispatch; plant clock advances by elapsed/forced time; intervening events → stale discard; incumbent retained on commitment failure. Not hard real-time preemption.

Realtime claims must use this contract (`advance_plant_during_optimize=True` or `timing_contract=...`). Instantaneous mode is diagnostic only.

## A5 Provenance

`docs/research_gate_4/matched_summary.json` stores `source_commit` = generating git HEAD at run time. Artifacts are separate versioned outputs; do not require the JSON’s commit field to equal a later commit that only re-stamps itself.

Workflow: `.github/workflows/gate4-data-integration.yml` downloads EVRP-TW-D, verifies data, runs Gate 4 tests + diagnostic.
