# Gate 3C — Testbed validation

## EVRP-TW-D (2-norm; native Q)

- Constructor: multi-vehicle due-date insertion with full recharge ([`testbed/constructor.py`](../../src/safe_time_evrp/testbed/constructor.py)).
- Validator: independent `evaluate_route` checks for payload, energy, windows, charge, depot return ([`testbed/validator.py`](../../src/safe_time_evrp/testbed/validator.py)).
- Probed: 60× Cus_5 + 40× Cus_15.
- **Feasible seeds: 60/60 Cus_5 (100%), 40/40 Cus_15 (100%)** under native battery — passes ≥70% Cus_5 criterion.
- Splits frozen in [`SPLITS.md`](SPLITS.md) / [`evrptwd_seeds.json`](evrptwd_seeds.json).
- Geometry label remains `evrp_tw_d_2norm_source` (no OSM claim).

## Amazon Last Mile (modeled electrification)

- Subset: 25 training routes with matching package + travel-time objects (unsigned S3 prefixes).
- Loader: [`data/amazon.py`](../../src/safe_time_evrp/data/amazon.py) — distances = `travel_time_h * assumed_speed` (not Euclidean lat/lng).
- Electrification: `esogu_light_cargo_v1` (40 kWh, 0.15 kWh/km, 11 kW); depot-colocated synthetic charger.
- Validation: 10/10 sampled routes with ≤10 customers admit feasible single-vehicle plans under the validator.
- Explicit: **not observed EV operations**.

## Charging contract

Gate 3C controllers use `recharge_policy=full` (adaptive charge-to-full at station visits). Fixed-target partial charge under Case P remains `UNKNOWN` in Part 2.5 certificates and is not claimed here.
