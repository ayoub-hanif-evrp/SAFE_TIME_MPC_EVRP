# MPC runtime profile

## Accounting rules

- Latency percentiles are **decision-level** from pooled `decide_seconds_raw`
  (not percentiles of per-episode means).
- Wall budget is **cooperative** (0.35s): ALNS is not hard-preemptive.
- CSS-MPC reserves a commit fraction (`commit_reserve_fraction≈0.20`) for final
  Validate + fallback emission; scoring stops at `score_deadline = deadline − reserve`.
- Report separately: **deadline overruns** (elapsed > budget) vs
  **cooperative_budget_hits** (scoring interrupted to preserve commit/fallback).

## Checkpointed optimization (remaining Phase-4 completion)

1. Deduplicate identical `FirstActionKey` candidates.
2. Checkpoint A: stage-0 Validate → empty-future terminal → empty causal score.
3. Checkpoint B: expand only top-K (`max_scenario_expansions=3`) with multi-scenario
   terminal + EV scoring; remaining empty-checkpoint candidates kept without full
   multi-scenario terminal probes (dominated-skip).
4. Terminal results cached by first-action key within a decide call.
5. Forecast-margin rule reuses empty-checkpoint scores (no duplicate empty B1).
6. ALNS share capped lower when a verified warm-start incumbent exists.

Hard interruptibility of ALNS remains unavailable; cooperative compliance is the
reported computational requirement.

## Corrected development campaign (pre-checkpoint SHA `cbbdd36`)

### CSS-MPC

```json
{
  "n": 999,
  "mean": 0.14665569409300844,
  "median": 0.0551528999931179,
  "p50": 0.0551528999931179,
  "p90": 0.35286980000091717,
  "p95": 0.38788599998224527,
  "p99": 0.5741249999846332,
  "max": 0.7187685000244528,
  "frac_over_budget": 0.23323323323323322
}
```

Deadline overruns (sum): 233

### Greedy-nominal

```json
{
  "n": 1032,
  "mean": 0.053388496995438794,
  "median": 0.006344349996652454,
  "p50": 0.006333999976050109,
  "p90": 0.21977299998980016,
  "p95": 0.2470958000048995,
  "p99": 0.3243602000293322,
  "max": 0.9567276999587193,
  "frac_over_budget": 0.009689922480620155
}
```

Deadline overruns (sum): 10

## Post-checkpoint microbench

See notes appended by `tests/test_css_mpc_runtime_checkpoint.py` / local smoke.
Historical campaign numbers above are preserved; they are **not** redefined to
declare prior overruns successful.
