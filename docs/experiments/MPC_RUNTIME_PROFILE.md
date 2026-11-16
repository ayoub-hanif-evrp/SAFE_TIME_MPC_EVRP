# MPC runtime profile

Decision-level latency from pooled `decide_seconds_raw` (not episode-mean percentiles).

## CSS-MPC

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

## Greedy-nominal

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

Cooperative 0.35s wall; ALNS not hard-preemptive.
