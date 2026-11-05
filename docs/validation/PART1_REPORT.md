# Part 1 report

Date: 5 November 2026. Package version 0.1.0.

## A. Implementation

Independent project in this directory. Python 3.12.10. Runtime dependencies are NumPy. Development dependencies are pytest, ruff, and matplotlib. OR-Tools is not used: the toy reference is exhaustive enumeration, which is exact for that family and does not need a solver license. SciPy is not used.

Layout:

- `src/safe_time_evrp/data`: download, verify, Schneider parser, structural checks, ARC CSV adapter
- `src/safe_time_evrp/models`: typed instance and decision state
- `src/safe_time_evrp/environment`: nominal energy, route evaluation, event simulator
- `src/safe_time_evrp/validation`: independent replay
- `src/safe_time_evrp/optimization`: insertion heuristic and toy enumeration
- `src/safe_time_evrp/controllers`: event-triggered MPC and the episode loop
- `src/safe_time_evrp/evaluation`: release generator, plot, development episode
- `tests`, `configs`, `docs`, `.github/workflows/ci.yml`

Commands:

```bash
python -m safe_time_evrp.data.download
python -m safe_time_evrp.data.verify
python -m safe_time_evrp.evaluation.smoke_test
python -m pytest -q
python -m ruff check src tests
```

Raw data and `experiments/development` outputs are gitignored. The manifest of hashes is committed.

## B. Data

EVRPTW-ARC, Zenodo [10.5281/zenodo.22800776](https://doi.org/10.5281/zenodo.22800776), version V1, creators Morgham and Belhor, license field Apache-2.0, access restricted, zero files, files endpoint HTTP 403. Not downloaded.

Schneider E-VRPTW, Mendeley [10.17632/h3mrm5dhxw.1](https://doi.org/10.17632/h3mrm5dhxw.1), version 1, deposited by Dominik Goeke, CC BY-NC 3.0. `evrptw_instances.zip`, 116,406 bytes, SHA-256 `54e305a03cc0aa8aba085d3e7fefc4e3357aba34357e0cd1f84c5b36c6c1df02`, matching the publisher hash. Parser: 92/92 instances, 5,960 customers, no failures. This is the operational foundation because ARC files were not available. It does not contain the Lille road attributes.

KU Leuven BEV energy dynamics, [10.48804/8KPDTW](https://doi.org/10.48804/8KPDTW), version 2, CC BY 4.0. Zip 162,310,975 bytes, MD5 `cc2d63758b411c0f8d4b61bdaa1fff1c` matching Dataverse, SHA-256 `97bcf4b914cd7312a08be49d53ae704a2450d39faa64d0c94d1294cd8eb92016`. Readme 2,004 bytes, MD5 `af00ec7244a6680beed61d34d4a8ed9b`, SHA-256 `fcd84aa6fc26f31f753889ba323b7a92d532426fbe5b06f174d51a5936206c46`. Extracted and not used as a routing benchmark.

## C. Correctness

`python -m pytest -q`: 12 passed, 0 failed.

Replay of the easy toy episode: accepted. Replay of the `c101C5` development episode: accepted. The corruption tests reject negative battery, missed windows, duplicate service, early access, impossible charging, interrupted travel, excess payload, a wrong arrival node, and a mislabeled denominator.

The information test excludes `C3` from every decision before its release at time 30. `Observation` has no hidden-request field.

Toy enumeration: `easy` serves 3/3 and the heuristic matches the count; `needs_two_charges` is feasible in the enumerated family and the heuristic misses it; a direct departure toward that customer is `proven_infeasible`, while a departure to the charger is `proven_feasible`; the impossible window cannot serve `C1`.

Not modeled: charger queues, payload-dependent energy, nonlinear charging, and calibrated kilowatt-hours.

## D. MPC baseline

Horizon: 1236 on the development instance, with accepted customers retained past the horizon and a depot return as the terminal condition. See `docs/formulation/INITIAL_MPC_BASELINE.md`.

The `c101C5` episode announced all five customers. It completed `C100`, `C12`, and `C85`, and rejected `C30` and `C64`. Service rate on the announced denominator: 0.6. Decisions: 20 (5 releases, 7 arrivals, 3 wait ends, 3 service ends, 1 charge end, 1 interval). Fallbacks: 0. Continuation failures: 0. Optimization wall clock: 0.00227 s. Simulation wall clock outside that sum: 0.00060 s. These are measurements on one run, not a deadline guarantee.

`v1` departed for `C100` at time 0 and arrived there at time 38.08. The release of `C12` at time 40 was given to `v2`. The completed travel kept its destination.

## E. Research readiness

Closest work: Basso et al. (2022) on safe learning for one electric vehicle under request and energy noise; Jiang, Zhang, and Puchinger (2026) on stochastic-request EV routing by rollout and deep Q-learning (abstract only); Sivagnanam et al. (2026) on prompt commitments and anytime improvement without a battery.

Worth studying in Part 2: a checkable terminal condition for accepted customers during a noninterruptible arc under interval energy; preservation of that condition after one arc and one partial recharge when the optimizer is not assumed to finish; a trigger time computed from the energy margin and the committed windows; an incumbent rule at a computation deadline that cannot drop an accepted customer.

Not proved: recursive feasibility, robustness to energy error, optimality of the insertion heuristic, or any advantage over the papers above.

Part 2 should decide the uncertainty set (design margin versus a model fit to the KU Leuven traces and, if access is later granted, ARC road attributes), the commitment rule (reject versus delay), and the terminal condition. The missing ARC files block road-dependent energy experiments. They do not block a nominal feasibility question on the Schneider physics. The direction is not empty: the toy already separates a proved continuation from a heuristic miss. It is also not a theorem yet.
