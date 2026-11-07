# Gate 3C — Causal experiment

Matched dynamic runs: identical releases (by `window.ready`), uncertainty (nominal energy), fleet sizes, and compute budgets. Results in [`causal_results.json`](causal_results.json) / [`causal_summary.json`](causal_summary.json).

## Aggregate (mean customers served)

| Pool | myopic | RH | rollout | flexibility |
| --- | ---: | ---: | ---: | ---: |
| EVRP-TW-D Cus_5 dev (8) | 4.125 | 4.125 | 4.125 | 4.125 |
| EVRP-TW-D Cus_5 held-out (8) | 4.500 | 4.500 | 4.500 | 4.500 |
| Amazon electrified (8×≤8 cust.) | 6.875 | 6.875 | 6.875 | 6.875 |

Commitment violations: 0 across controllers in these runs.

## Present-action divergence

- **EVRP-TW-D:** flexibility first actions **identical** to RH and rollout (0% divergence).
- **Amazon:** flexibility differs from RH on **1/8** routes (12.5%); on that case first action is `AA` vs RH `AH`.
- **Flexibility vs rollout:** **0%** action divergence on all pools (`flex_vs_rollout_action_frac = 0`).

### Case study (Amazon `…85264f0a3944`)

| Controller | First action | Served |
| --- | --- | ---: |
| RH open-loop | AH service | 8 |
| Rollout | AA service | 8 |
| Flexibility MPC | AA service | 8 |

Flexibility **does** change the present action relative to ordinary RH, but selects the **same** action as the strong PI rollout and does **not** improve service.

## Microscope toy

`mpc3c/causal_toy.py` energy-fork instance: all four controllers chose the same first action (`A` service) under the shared constructive generator — no additional separation.

## Interpretation

The flexibility terminal, as implemented on top of the same insertion candidate set as rollout, does not produce a distinct decision policy or outcome advantage. Per Gate 3C stop rule: **reject the proposed novelty**.
