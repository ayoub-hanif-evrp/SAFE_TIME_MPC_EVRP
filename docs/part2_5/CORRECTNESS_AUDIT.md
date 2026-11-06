# Part 2.5 correctness audit

Base revision audited: `4beb9163471a7f45fe933ed3fe969c9390d55b0b`.  
Formatting repair pushed as `ef3ba74894254b0034373c5b9252b0897008fa24` (GitHub Actions run 42298760659: **success**).  
Correctness repair commit: `b366853ca43a5d899d7bd0e48d643020307b3e7c` (plus follow-up rejection/service repair on the same branch).  
Local verification: `ruff format` / `ruff check` / `ruff format --check` clean; Schneider verify 92 / 5960; smoke `c101C5` completed C100, C12, C85.

## CI restoration

Three robust modules were reformatted. No assertions or lint rules were relaxed. The Actions run for the format commit completed successfully.

## Certificate soundness

Counterexample P (fixed-target partial charging) was confirmed against `evaluate_route` and the certificate:

| Corner | Arrival SOC at charger | Charge to 8 | Result |
| --- | --- | --- | --- |
| Energy ×2 | 6 | allowed | feasible |
| Energy ×0.5 | 9 | rejected (`impossible_charge`) | infeasible |

The old Proposition 1 would have labeled the upper corner `certified_feasible`. That claim is **withdrawn** for fixed-target partial charging with a non-degenerate energy interval. The code now returns `UNKNOWN` / `fixed_partial_target_not_monotone`. Proposition 1 is narrowed to **full recharge** (or degenerate energy bounds). See `CERTIFICATE_COUNTEREXAMPLES.md` and the updated `docs/part2/FEASIBILITY_PROOFS.md`.

No adaptive “charge at least to target” plant was introduced.

## Incremental cache

The validity key now includes plant model version, instance identity, recharge policy, battery parameters, anchor, full uncertainty rectangle, inflation, and the route signature **with charge targets**. A mismatched uncertainty, anchor, or charge target forces a miss. Prefix reuse remains a standard cache, not a novelty claim.

## Fleet and acceptance

Fleet certification rejects duplicate service and unknown vehicle ids. Newly accepted customers are included in the required set before a candidate may be staged.

## Real-time semantics

If a physical or information event is due before optimization finishes, the candidate is discarded, plant time does not jump past that event, and no new control action is applied until after the event is processed. Observation versions include physical action identity, request partitions, and uncertainty bounds. Details: `REAL_TIME_SEMANTICS.md`.

## Disturbed plant

`ArcDisturbanceSampler` is a separately versioned plant mode. Realized factors are logged on every depart. Replay validates those factors. Schneider files are unchanged. KU Leuven traces are not used as truck delivery measurements.

## Test counts (this audit branch, after correctness fixes)

Recorded after the certificate/runtime repairs and before or with the development study:

```text
python -m pytest -q   # 38 passed (Part 1 + Part 2 + Part 2.5 correctness)
```

Development study after the repairs: 39 rows on `c101C5`, `r104C5`, `rc105C5`; see `DEVELOPMENT_RESULTS.md`.
