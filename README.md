# SAFE-TIME MPC for dynamic electric vehicle routing

Part 1 foundation for a feasibility-preserving, computation-aware model predictive controller on the dynamic electric vehicle routing problem.

The controller in this repository is a deterministic event-triggered baseline. It is a working receding-horizon loop with an insertion heuristic. It is not a new algorithm, and it does not prove recursive feasibility.

Part 1 is the verified simulator, the information boundary, and a deterministic insertion MPC. Part 2 adds an exact rectangle certificate for that plant, a backup that commits only after a fresh certificate, a process-level solver deadline, and a validity-aware trigger. The trigger's proved property is that a still-valid backup does not need another solve in order to stay feasible. That is not a new self-triggered stability theorem. See `docs/part2/PART2_RESEARCH_DECISION.md`.

## Scope

- Nominal Schneider et al. (2014) physics: Euclidean distance as defined by the deposited readme, energy `r * distance`, recharge time `g` per unit of energy, hard windows on the start of service, full recharge by default.
- Event-driven multi-vehicle simulation, independent log replay, and dynamic releases that are not conditioned on an offline route.
- A rectangular travel-time and energy certificate for a fixed sequence, a certified backup, and a deadline enforced by a separate process.

Part 3 (large comparisons and holdout evaluation) is not implemented and is not justified by the Part 2 theory result.

## Data licences

The Schneider instances are CC BY-NC 3.0, deposited by Dominik Goeke, DOI [10.17632/h3mrm5dhxw.1](https://doi.org/10.17632/h3mrm5dhxw.1). They are downloaded into `data/raw` and are not part of this source tree.

The KU Leuven BEV energy-dynamics archive is CC BY 4.0, DOI [10.48804/8KPDTW](https://doi.org/10.48804/8KPDTW). It is a calibration source, not a routing benchmark.

EVRPTW-ARC, DOI [10.5281/zenodo.22800776](https://doi.org/10.5281/zenodo.22800776), was restricted when queried (no public files, files endpoint HTTP 403). This project does not substitute another road dataset for it.

See `docs/datasets/DATA_PROVENANCE.md`.

## Commands

Python 3.11 or newer.

```bash
pip install -e ".[dev]"
python -m safe_time_evrp.data.download
python -m safe_time_evrp.data.verify
python -m pytest -q
python -m safe_time_evrp.evaluation.smoke_test
python -m safe_time_evrp.robust.pilot
```

`robust.pilot` runs one development episode for the nominal baseline and the robust trigger policies. If `experiments/development/part2_pilot/manifest.json` is already marked completed, the command does not overwrite it. Delete that manifest to run again. The output is gitignored.

The certified controller is `safe_time_evrp.robust.controller.SafeTimeController`. The deadline supervisor is `safe_time_evrp.robust.supervisor.SolverSupervisor`. Trigger names are `fixed_period`, `every_event`, `slack_heuristic`, and `validity_aware`.

`download` is idempotent: a file whose publisher checksum already matches is kept. A checksum mismatch fails. A restricted ARC record is reported as `access_restricted` and is not replaced by a different dataset.

The development episode writes a manifest, a service summary, decisions, a trajectory, and a route/state-of-charge figure under `experiments/development/`. Those outputs are gitignored.

## Documentation

- `docs/literature/PRIOR_ART_AND_RESEARCH_GAP.md`
- `docs/formulation/PROBLEM_DEFINITION.md`
- `docs/formulation/INITIAL_MPC_BASELINE.md`
- `docs/datasets/DATA_PROVENANCE.md`
- `docs/datasets/DATA_COMPATIBILITY.md`
- `docs/validation/PHYSICAL_VALIDATION.md`
- `docs/validation/INFORMATION_BOUNDARY.md`
- `docs/validation/EXACT_TOY_CASES.md`
- `docs/validation/PART1_REPORT.md`
- `docs/part2/FOUNDATION_AUDIT.md`
- `docs/part2/NOVELTY_AND_THEORY_GAP.md`
- `docs/part2/MATHEMATICAL_FORMULATION.md`
- `docs/part2/FEASIBILITY_PROOFS.md`
- `docs/part2/PART2_RESEARCH_DECISION.md`
