# Schneider-derived dynamic EVRPTW — results analysis

**Benchmark:** Schneider-derived dynamic EVRPTW  
**Protocol:** `2026-11-14.v1`  
**Tier:** `scale`  
**Dynamicity:** `medium`  
**Rows:** 3  
**Wall seconds (runner):** 2028.0472747999593  

## Controllers (unchanged)

b1, m1, stochastic_mpc, cce_mpc, cce_no_forecast

## Mean completed services

- **b1**: mean=0.5, n=2, approx 95% CI half-width=0.9799999999999999
- **m1**: mean=8.5, n=2, approx 95% CI half-width=6.859999999999999
- **stochastic_mpc**: mean=0.5, n=2, approx 95% CI half-width=0.9799999999999999
- **cce_mpc**: mean=1.0, n=2, approx 95% CI half-width=1.9599999999999997
- **cce_no_forecast**: mean=4.0, n=2, approx 95% CI half-width=3.9199999999999995

## Paired differences (CC-E-MPC)

- vs B1 completed: {'n': 2, 'mean': 0.5, 'std': 0.7071067811865476, 'ci95_halfwidth': 0.9799999999999999}
- vs stochastic MPC completed: {'n': 2, 'mean': 0.5, 'std': 0.7071067811865476, 'ci95_halfwidth': 0.9799999999999999}

## Failures

```json
{
  "b1:exception": 1,
  "m1:exception": 1,
  "stochastic_mpc:exception": 1,
  "cce_mpc:exception": 1,
  "cce_no_forecast:exception": 1
}
```

## By customer count

```json
{
  "100": {
    "b1": {
      "n": 2,
      "mean": 0.5,
      "std": 0.7071067811865476,
      "ci95_halfwidth": 0.9799999999999999
    },
    "m1": {
      "n": 2,
      "mean": 8.5,
      "std": 4.949747468305833,
      "ci95_halfwidth": 6.859999999999999
    },
    "stochastic_mpc": {
      "n": 2,
      "mean": 0.5,
      "std": 0.7071067811865476,
      "ci95_halfwidth": 0.9799999999999999
    },
    "cce_mpc": {
      "n": 2,
      "mean": 1.0,
      "std": 1.4142135623730951,
      "ci95_halfwidth": 1.9599999999999997
    },
    "cce_no_forecast": {
      "n": 2,
      "mean": 4.0,
      "std": 2.8284271247461903,
      "ci95_halfwidth": 3.9199999999999995
    }
  }
}
```

## By family

```json
{
  "r": {
    "b1": {
      "n": 1,
      "mean": 1.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "m1": {
      "n": 1,
      "mean": 12.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "stochastic_mpc": {
      "n": 1,
      "mean": 1.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "cce_mpc": {
      "n": 1,
      "mean": 2.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "cce_no_forecast": {
      "n": 1,
      "mean": 2.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    }
  },
  "rc": {
    "b1": {
      "n": 1,
      "mean": 0.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "m1": {
      "n": 1,
      "mean": 5.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "stochastic_mpc": {
      "n": 1,
      "mean": 0.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "cce_mpc": {
      "n": 1,
      "mean": 0.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    },
    "cce_no_forecast": {
      "n": 1,
      "mean": 6.0,
      "std": 0.0,
      "ci95_halfwidth": 0.0
    }
  }
}
```

## Scientific reading (scalability tier)

Predeclared stems `c101_21`, `r101_21`, `rc101_21` (chosen before seeing scores).

- `c101_21`: **all five controllers** failed with decision-loop stall (not replaced).  
- `r101_21` / `rc101_21`: episodes finished under `t_max` cutoffs with very low completed
  counts for B1 / stochastic / CC-E-MPC; M1 and CC-E-MPC-without-forecast served more
  customers on these two runs but this is a tiny n=1×2 slice.  

**Conclusion:** under the frozen 0.35 s ALNS budget, 100-customer Schneider-derived
dynamic episodes are not a reliable superiority arena. Report timeouts/stalls; do not
swap in easier instances. Assessment remains `INCREMENTAL_RESULT`.
