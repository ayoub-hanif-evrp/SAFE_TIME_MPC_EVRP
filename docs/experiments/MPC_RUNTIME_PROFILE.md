# MPC runtime profile

Decision-level latency from pooled `decide_seconds_raw` (not episode-mean percentiles).

## CSS-MPC

```json
{
  "n": 913,
  "mean": 0.1699252238762101,
  "median": 0.07651039998745546,
  "p50": 0.07651039998745546,
  "p90": 0.37309849995654076,
  "p95": 0.5088848000159487,
  "p99": 0.7284910000162199,
  "max": 1.010608599986881,
  "frac_over_budget": 0.11062431544359255
}
```

Deadline overruns (sum): 101

## Greedy-nominal

```json
{
  "n": 1001,
  "mean": 0.06847369630221412,
  "median": 0.009022600017488003,
  "p50": 0.009022600017488003,
  "p90": 0.23770489997696131,
  "p95": 0.26604340004269034,
  "p99": 0.5626011000131257,
  "max": 1.3455788999563083,
  "frac_over_budget": 0.029970029970029972
}
```

Deadline overruns (sum): 30

Cooperative 0.35s wall; ALNS not hard-preemptive.
