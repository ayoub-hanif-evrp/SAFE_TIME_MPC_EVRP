# Schneider-derived dynamic EVRPTW — results analysis

**Benchmark:** Schneider-derived dynamic EVRPTW  
**Protocol:** `2026-11-14.v1`  
**Tier:** `small`  
**Dynamicity:** `medium`  
**Rows:** 180  
**Wall seconds (runner):** 5871.145869  

## Controllers (unchanged)

b1, m1, stochastic_mpc, cce_mpc, cce_no_forecast

## Mean completed services

- **b1**: mean=5.252941176470588, n=170, approx 95% CI half-width=0.6265784009499592
- **stochastic_mpc**: mean=3.0892857142857144, n=112, approx 95% CI half-width=0.5055527257948063
- **cce_mpc**: mean=5.418803418803419, n=117, approx 95% CI half-width=0.5442511162341314
- **m1**: mean=5.716981132075472, n=159, approx 95% CI half-width=0.5771440700000212
- **cce_no_forecast**: mean=6.064285714285714, n=140, approx 95% CI half-width=0.6208282006129062

## Paired differences (CC-E-MPC)

- vs B1 completed: {'n': 112, 'mean': 0.5982142857142857, 'std': 3.444436227692556, 'ci95_halfwidth': 0.6379185165707166}
- vs stochastic MPC completed: {'n': 66, 'mean': 2.8333333333333335, 'std': 3.998397114742292, 'ci95_halfwidth': 0.9646505782669379}

## Failures

```json
{
  "m1:exception": 21,
  "cce_no_forecast:exception": 40,
  "stochastic_mpc:exception": 68,
  "cce_mpc:exception": 63,
  "b1:exception": 10
}
```

## By customer count

```json
{
  "10": {
    "b1": {
      "n": 57,
      "mean": 5.9298245614035086,
      "std": 3.5043832202523117,
      "ci95_halfwidth": 0.9097671174888767
    },
    "stochastic_mpc": {
      "n": 34,
      "mean": 5.117647058823529,
      "std": 3.328159978329576,
      "ci95_halfwidth": 1.1187184657264324
    },
    "cce_mpc": {
      "n": 32,
      "mean": 6.5625,
      "std": 2.5770388107783835,
      "ci95_halfwidth": 0.8928983930563325
    },
    "m1": {
      "n": 51,
      "mean": 6.882352941176471,
      "std": 2.5584922030252852,
      "ci95_halfwidth": 0.7021907126993018
    },
    "cce_no_forecast": {
      "n": 46,
      "mean": 7.391304347826087,
      "std": 2.6539552107881486,
      "ci95_halfwidth": 0.7669565217391304
    }
  },
  "5": {
    "b1": {
      "n": 58,
      "mean": 3.1206896551724137,
      "std": 1.4994453501667613,
      "ci95_halfwidth": 0.3858981675890502
    },
    "m1": {
      "n": 54,
      "mean": 3.037037037037037,
      "std": 1.4401645996461911,
      "ci95_halfwidth": 0.38412389405085906
    },
    "stochastic_mpc": {
      "n": 28,
      "mean": 2.3214285714285716,
      "std": 1.2488089563755576,
      "ci95_halfwidth": 0.46256531070397683
    },
    "cce_mpc": {
      "n": 60,
      "mean": 3.75,
      "std": 1.1878623443617289,
      "ci95_halfwidth": 0.30057064371692516
    },
    "cce_no_forecast": {
      "n": 52,
      "mean": 3.5961538461538463,
      "std": 1.49849094529202,
      "ci95_halfwidth": 0.4072944784836542
    }
  },
  "15": {
    "b1": {
      "n": 55,
      "mean": 6.8,
      "std": 5.608855432194634,
      "ci95_halfwidth": 1.4823439078970375
    },
    "m1": {
      "n": 54,
      "mean": 7.296296296296297,
      "std": 4.656622914425843,
      "ci95_halfwidth": 1.2420247848441452
    },
    "stochastic_mpc": {
      "n": 50,
      "mean": 2.14,
      "std": 2.1093571900230743,
      "ci95_halfwidth": 0.5846839830198873
    },
    "cce_mpc": {
      "n": 25,
      "mean": 7.96,
      "std": 4.015387071420803,
      "ci95_halfwidth": 1.5740317319969548
    },
    "cce_no_forecast": {
      "n": 42,
      "mean": 7.666666666666667,
      "std": 4.976366911942529,
      "ci95_halfwidth": 1.5050253669003557
    }
  }
}
```

## By family

```json
{
  "c": {
    "b1": {
      "n": 57,
      "mean": 5.456140350877193,
      "std": 4.313890253913168,
      "ci95_halfwidth": 1.1199218963225634
    },
    "stochastic_mpc": {
      "n": 33,
      "mean": 3.1515151515151514,
      "std": 2.72856661226655,
      "ci95_halfwidth": 0.9309656607653874
    },
    "cce_mpc": {
      "n": 39,
      "mean": 4.948717948717949,
      "std": 2.8372403006472213,
      "ci95_halfwidth": 0.8904712204382986
    },
    "m1": {
      "n": 55,
      "mean": 6.1454545454545455,
      "std": 3.8558189878857214,
      "ci95_halfwidth": 1.0190403114757587
    },
    "cce_no_forecast": {
      "n": 50,
      "mean": 6.1,
      "std": 4.248649245132301,
      "ci95_halfwidth": 1.1776654873095331
    }
  },
  "r": {
    "b1": {
      "n": 55,
      "mean": 5.527272727272727,
      "std": 3.650745968695457,
      "ci95_halfwidth": 0.9648423125532233
    },
    "m1": {
      "n": 50,
      "mean": 5.48,
      "std": 2.858856628879769,
      "ci95_halfwidth": 0.7924346282186311
    },
    "stochastic_mpc": {
      "n": 34,
      "mean": 3.176470588235294,
      "std": 2.5991908791740292,
      "ci95_halfwidth": 0.8736848142555728
    },
    "cce_no_forecast": {
      "n": 42,
      "mean": 5.9523809523809526,
      "std": 3.207859106391303,
      "ci95_halfwidth": 0.9701674763922581
    },
    "cce_mpc": {
      "n": 37,
      "mean": 6.081081081081081,
      "std": 3.1391645949765605,
      "ci95_halfwidth": 1.011507941581998
    }
  },
  "rc": {
    "b1": {
      "n": 58,
      "mean": 4.793103448275862,
      "std": 4.502469578453605,
      "ci95_halfwidth": 1.1587583100360765
    },
    "m1": {
      "n": 54,
      "mean": 5.5,
      "std": 4.254852945156349,
      "ci95_halfwidth": 1.1348638081430054
    },
    "cce_mpc": {
      "n": 41,
      "mean": 5.2682926829268295,
      "std": 3.0002032451477554,
      "ci95_halfwidth": 0.9183639333612523
    },
    "cce_no_forecast": {
      "n": 48,
      "mean": 6.125,
      "std": 3.7052291972636886,
      "ci95_halfwidth": 1.0482153864802315
    },
    "stochastic_mpc": {
      "n": 45,
      "mean": 2.977777777777778,
      "std": 2.8800953968487732,
      "ci95_halfwidth": 0.8415049743009771
    }
  }
}
```

## Scientific reading

This analysis does not retune controllers. Numbers exclude controller crashes from
the completed-service means, so **unconditional** superiority claims are not valid when
failure rates differ.

### Coverage (medium dynamicity, 36×5 = 180 episodes)

| Controller | Episodes with metrics | Exception failures |
|------------|----------------------:|-------------------:|
| B1 | 170 | 10 |
| M1 | 159 | 21 |
| CC-E-MPC (no forecast) | 140 | 40 |
| CC-E-MPC | 117 | 63 |
| Stochastic MPC | 112 | 68 |

Dominant failure mode: `RuntimeError: decision loop did not advance time` (plant/control
stall under the fixed ALNS budget), recorded as computational/control failure — not
relabeled as success.

### Paired completed-service cells (both controllers produced metrics)

- **CC-E-MPC vs B1** (n=112): better 49 / worse 31 / tie 32; mean Δ completed ≈ **+0.60**
  (approx 95% CI half-width ≈ 0.64 — includes zero).
- **CC-E-MPC vs stochastic MPC** (n=66): better 41 / worse 6 / tie 19; mean Δ ≈ **+2.83**,
  but stochastic MPC fails much more often, so this contrast is **survivorship-biased**.

### Assessment impact

Broader Schneider-derived evidence **does not overturn** the existing
`INCREMENTAL_RESULT` label. It replaces the toy-only gap with a more credible workload,
but also exposes high instability for forecast-using controllers under the frozen budget.
Any mean gains versus B1 are modest, uncertain, and conditional on non-crashing runs.
No algorithm changes were made to improve these scores.

The prior synthetic holdout `B_adversarial_overaccept` remains already-evaluated and is
not presented as fresh unseen validation.
