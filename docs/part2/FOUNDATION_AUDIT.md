# Part 1 foundation audit

Audited before any Part 2 controller was added. The audit ran the code. It did not treat the Part 1 documents as evidence.

## Revision and environment

| Item | Value |
| --- | --- |
| Git revision audited | `a90e919b084bbda4211bfd3ba5335ce11730a45a` |
| Branch | `master`, clean working tree at the start of the audit |
| Python | 3.12.10 |
| Operating system | Windows 10.0.26200 |
| Tests | `python -m pytest -q` — 12 passed |
| Dataset check | `python -m safe_time_evrp.data.verify` — Schneider instances 92, customers 5960, ARC status `access_restricted` |
| End-to-end episode | `python -m safe_time_evrp.evaluation.smoke_test` on `c101C5`, fleet 2. Completed `C100`, `C12`, `C85`. 20 decisions. Replay accepted the log. |

The Schneider archive checksum is the one recorded in `data/manifests/source_manifest.json` (zip SHA-256 `54e305a03cc0aa8aba085d3e7fefc4e3357aba34357e0cd1f84c5b36c6c1df02`). The files were already on disk and matched. No re-download was required.

## Checks

1. **EVRPTW-ARC.** The Zenodo record is access-restricted. The verified fallback is Schneider et al. (2014) as deposited by Goeke. The adapter does not invent road energy.
2. **Checksums.** The verifier reports 92 instances and 5960 customers. That matches the manifest.
3. **Dynamics.** Travel, service, charging, load, and battery updates are in `environment/physics.py` and `environment/simulator.py`. Service must start inside the window. Waiting is allowed. Freight for a tour is loaded at the depot.
4. **Non-interruptible actions.** Travel, service, and charging are not restarted. Waiting can be cancelled. A decision for a busy vehicle replaces only its stored suffix.
5. **Commitments.** Request statuses are hidden, announced, deferred, accepted, in service, completed, rejected, and accepted-but-unfulfilled. Part 1 acceptance is a heuristic insertion decision, not a robust promise.
6. **Information boundary.** `Observation` has no field for hidden future releases. The smoke scenario uses indexed staggering, not an offline route.
7. **MPC baseline.** `EventTriggeredMPC.decide` builds a route, keeps a previous suffix when the new construction drops an accepted customer, and the episode executes the first idle action. The fallback is explicitly not a certificate.
8. **Independent feasibility check.** `validation/replay.py` does not call `evaluate_route`.
9. **Benchmark assumptions.** Euclidean distance, energy `r * distance`, full recharge time `g * (Q - soc)`, hard windows on service start. Documented in `docs/datasets/` and `docs/formulation/`.
10. **No clairvoyant plan.** Releases are scheduled by the dynamic generator. The controller never reads the hidden list.

Part 1 is complete enough to support a certificate and a second controller. The audit did not stop.

## Modeling limits that Part 2 must not paper over

- No road network. EVRPTW-ARC was not available.
- Energy does not depend on payload, slope, or temperature. The KU Leuven traces are a calibration source and are not used.
- No station queues, station closures, or battery aging.
- The insertion heuristic is not exact. The toy `needs_two_charges` is a known miss.
- Fleet size is a scenario choice. Schneider files do not fix it.
- Waiting is interruptible, so a replan can cancel a wait.
- Part 1 has no process-level solver deadline. Optimization time is a measurement, and the plant does not advance during it.
- A previous feasible suffix is an incumbent, not a proof that the closed loop stays feasible.
- A zero-duration charge could schedule another charge at the same instant. Part 2 skips that action in the plant (`charge_skip` when the battery is already at the target).

## Frozen records

Part 1 development outputs under `experiments/development/c101C5/` are gitignored. The smoke command rewrote that folder during this audit. Part 2 writes only under `experiments/development/part2_pilot/`.
