# Data compatibility

## What the internal instance stores

`Instance` holds nodes, a complete directed arc table, and one vehicle type. Schneider arcs set `distance_definition` to `euclidean_source_definition`. Optional road fields (`slope_mean_pct`, elevation, road type, traffic, temperature, driving style) stay `None`.

Both directions are stored. For Schneider they are symmetric because Euclidean distance is symmetric. The checker still requires the reverse arc to exist. Asymmetry will matter when an ARC table is loaded.

## Checks that ran on all 92 files

`validate_instance` checks one depot, unique ids, the arc count `n(n-1)`, nonnegative distance, time, and energy, windows, nonnegative demand and service, zero demand off customers, positive `Q`, `C`, `v`, and `g`, and the identities `distance = hypot`, `energy = r * distance`, and `travel_time = distance / v`.

Examples from the verification report:

| Instance | Customers | Stations | Arcs | Arcs with energy above `Q` | `Q` | `C` |
| --- | --- | --- | --- | --- | --- | --- |
| `c101C5` | 5 | 3 | 72 | 0 | 77.75 | 200 |
| `c101C10` | 10 | 5 | 240 | 2 | 77.75 | 200 |
| `c101_21` | 100 | 21 | 14,762 | 570 | 79.69 | 200 |
| `r101_21` | 100 | 21 | 14,762 | 786 | 62.14 | 200 |
| `rc101_21` | 100 | 21 | 14,762 | 1,028 | 79.69 | 200 |

An arc that exceeds the battery is a property of the benchmark, not a parse error.

## ARC adapter

`load_arc_table` reads a CSV only when the columns named in the Zenodo data dictionary are present, including `distance_km`, `time_h`, and the slope and elevation fields. It does not create an energy column. The unit test uses a synthetic CSV and does not claim that file is the Zenodo record.

## Fleet size

The Schneider files do not fix the number of vehicles. Scenarios set `fleet_size`. That is an assumption of the dynamic problem, recorded in the scenario file.

## Charging

The baseline policy is `full`, matching the 2014 scheme: on a charger visit the target is `Q` and the duration is `g * (Q - soc)`. `with_recharge_policy("partial")` keeps the same rate and uses the visit's target. No queue is added.

## Units

Do not interpret `Q` as a kilowatt-hour or a coordinate unit as a kilometre. The KU Leuven traces are the place to calibrate a later energy model, and that calibration is not part of Part 1.
