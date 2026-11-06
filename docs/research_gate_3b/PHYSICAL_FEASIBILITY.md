# Physical feasibility pilot (Gate 3B)

## Setup

- Archive: `EVRP-TW-D-B-v1.0.tar.gz` (MD5 match; SHA-256
  `02da7522652daf3a1a00211a84e984f714002b3e200cf2f860b5a66376bc9fcb`).
- Instances: anchored `Cus_5` (20 files) and `Cus_15` (10 files).
- Distances: release **2-norm** (not road-network tables — absent from archive).
- Vehicle: instance-native `(Q,r,g,v)` and scaled batteries at fractions
  `{1.0, 0.5, 0.25, 0.125}`.
- Replay: independent of optimizers (`safe_time_evrp.pilot.feasibility`).
- Route probe: nearest-neighbor customer tour; optional midpoint charger insert.
- Splits: treat anchored Cus_5 as development probe and Cus_15 as harder scale;
  held-out Cus_100 / unanchored reserved (not claimed).

## Aggregate (from `pilot_results.json`)

| Battery fraction | energy > Q (NN tour) | NN energy-only fail | Midpoint charge rescues energy | NN full (TW+energy) fail |
| --- | ---: | ---: | ---: | ---: |
| 1.0 (native) | 53% | 53% | 33% | 100% |
| 0.5 | 100% | 100% | 7% | 100% |
| 0.25 | 100% | 100% | 0% | 100% |
| 0.125 | 100% | 100% | 0% | 100% |

## Interpretation

1. **Energy is active under native parameters.** About half of NN tours exceed `Q`;
   inserting a public charger changes energy feasibility for a third of instances.
   Battery limits are not vacuous on this release.
2. **Time windows dominate constructive infeasibility.** NN almost never meets narrow
   windows; that is a routing/TW issue, not proof that charging is irrelevant.
3. **Do not manufacture urgency with tiny batteries.** At ≤25% of native `Q`, energy
   always fails and midpoint charge rarely restores feasibility — too aggressive for
   a fair MPC story.
4. **Road-network claim not supported by files.** Any “real geography EVRP” paper must
   either obtain true network layers or honestly state 2-norm semi-synthetic geometry.
5. **Dynamic demand.** LaDe accept timestamps provide a non-EV release process that can
   be overlaid later; not mixed into this static pilot.

## Stop condition

We do **not** stop: energy and charging change feasibility often enough under native
`Q` to justify studying online energy-aware control. We **do** stop claiming the
Zenodo road-network story until matching files exist.
