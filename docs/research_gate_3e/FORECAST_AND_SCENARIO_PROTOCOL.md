# Gate 3E — Forecast and scenario protocol

## Train-only model

Atoms = customer `(x, y, demand, service, ready, due)` from Gate 3C Cus_5 **train** files only.

Inter-arrival mean = empirical ready gaps on that pool.

## Scenario sampling

Independent stream: `forecast_seed_for(instance_name)` via SHA-256.

Each scenario draws `customers_per_scenario` anonymous demands with location jitter; ready times from the inter-arrival model.

Plant releases use a **separate** stream: `release_seed_for(instance_name)`.

## Nonanticipativity

Only scenario customers with `ready ∈ [now, now+H]` enter the planning observation. Realization of the live episode is never copied into scenarios.

## Labels

The Gate 3C/3D “rollout” controller is a **deterministic prefix-search** policy, not a stochastic policy-tree rollout. Stochastic multi-scenario lookahead is **not** claimed as implemented here.
