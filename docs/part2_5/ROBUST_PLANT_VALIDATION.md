# Robust plant validation (Part 2.5)

## Mode

`environment/disturbance.py` defines `ArcDisturbanceSampler` (`disturbance_v1`). It is separate from the Schneider tables. Modes: `nominal`, `upper`, `lower`, `mixed`, `adversarial_energy`, `adversarial_time`, `out_of_set`.

Factors are drawn when an arc is **dispatched**, recorded on the depart event (`time_factor`, `energy_factor`, nominal values), and never exposed to the controller as a future stream.

## Replay

`validation/replay.py` accepts logged factors. When `energy_factor` / `time_factor` are present, it checks that logged energy and travel time equal factor times the nominal arc tables and that SOC and arrival timing match. Global `energy_scale` remains for older nominal logs.

## Checks performed

- Upper-bound realizations log factor 1.1 (in the unit test) and replay as `ok`.
- Out-of-set mode labels `in_set=False` and exceeds the rectangle.
- Mixed mode uses a deterministic seed.
- Schneider instance files are not rewritten.
- KU Leuven BEV traces are **not** used here as measurements of Schneider delivery trucks. Any future calibration must document that assumption explicitly and separately.

## Information boundary

The observation type is unchanged: no hidden releases, no future disturbance sequence. The sampler history lives only on the plant side.
