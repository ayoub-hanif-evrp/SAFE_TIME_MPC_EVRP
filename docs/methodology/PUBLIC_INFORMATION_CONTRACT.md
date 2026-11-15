# Public information contract (Stage 1C)

## Decision

For Schneider-derived EVRPTW-D episodes in this repository, the **static customer
population size** \(N = |\text{customers}|\) is treated as **public**.

Rationale: the static Schneider instance is the known problem statement; dynamics
are announcement times of those customers. Controllers already receive the full
`Instance` object for geometry of *released* planning, but unreleased customer
**identities, coordinates, and windows** remain hidden for forecast construction.

## Observation field

`Observation.public_customer_count: int | None`

- Set by `FleetSimulator.observation()` from `len(instance.customer_ids())`.
- Finite-demand remaining-count uses this field, **not** a silent re-read that
  could be confused with leaking attributes.
- Forecast customers remain anonymous (`syn_*`) and sample train atoms only.

## Consistency requirement

All controllers in a comparison must see the same `public_customer_count` on the
same observation. Hidden future attribute changes that preserve public fields
must not change online decisions (regression test).
