# Gate 3E — Information boundary

## Rule

At decision time, controllers may use:

- The current `Observation` (released / accepted / completed / rejected / in service).
- A forecast model fitted on **train-split only**.
- Anonymous scenario samples (`syn_*`) with coordinates/timing drawn from train atoms + jitter.

Controllers must **not** read unreleased evaluation customer IDs, locations, or windows from the live `Instance` when building forecasts.

## Implementation

- `fit_empirical_arrivals(train_instances)` stores `TrainDemandAtom`s.
- `build_anonymous_scenarios` samples `syn_s{i}_{k}` only.
- `augment_instance_for_planning` attaches synthetic nodes to a **planning clone**.
- Plant `Instance` is unchanged; dispatch strips any residual unreleased services and revalidates.

## Proof test

Two environments share the same released history (customer A) and the same forecast seed/model but differ in hidden customer `H` geometry. RH decisions match; forecast IDs never equal `H`.
