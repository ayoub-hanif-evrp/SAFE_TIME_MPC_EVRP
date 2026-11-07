# Gate 3D — Research decision

## Verdict: **REVISE**

## Decision rule applied

| Criterion | Status |
| --- | --- |
| Harness scientifically valid (simulator execution, replay, no microtrips/desync) | **Met** |
| Predictive horizon changes present action on microscope | **Met** |
| Repaired comparison: flexibility ≠ rollout with measurable service/commitment/energy benefit | **Not met** |

Per Gate 3D rule:

- **GO** would require harness + horizon causality + flexibility distinct benefit.
- **REVISE:** harness correct and predictive horizon matters, but flexibility still equals rollout / no benefit → **keep platform; change or abandon flexibility terminal.**
- **NO-GO** would require predictive control never changing present actions, or energy never decision-relevant. That is **not** the case after repair (microscope + RH vs myopic service gap + Amazon charges).

## What was repaired

1. Closed-loop harness → `FleetSimulator` / `dispatch_suffix` / event queue (`EXECUTION_CONTRACT.md`).
2. Information boundary + forecast scenarios (`forecast.py`, flexibility remaining-set fix).
3. Amazon UTC windows + energy-active electrification; fleet-matched EVRP-TW-D seeds.

## What remains false as a novelty claim

The Gate 3C flexibility terminal, even with corrected information, still selects the **same** action sequences as the strong rollout baseline on the matched re-test and does not improve service or commitment metrics.

## Allowed next step (not Part 3)

A later **mechanism** gate may replace or abandon the flexibility terminal while reusing this closed-loop platform. Do **not** invent a new mechanism inside Gate 3D documentation scope beyond this decision. Do **not** start Part 3 on the flexibility-terminal hypothesis.
