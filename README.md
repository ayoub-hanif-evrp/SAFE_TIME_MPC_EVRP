# SAFE-TIME MPC for dynamic electric vehicle routing

Part 1 foundation for a feasibility-preserving, computation-aware model predictive controller on the dynamic electric vehicle routing problem.

The controller in this repository is a deterministic event-triggered baseline. It is a working receding-horizon loop with an insertion heuristic. It is not a new algorithm, and it does not prove recursive feasibility.

## Scope

- Nominal Schneider et al. (2014) physics: Euclidean distance as defined by the deposited readme, energy `r * distance`, recharge time `g` per unit of energy, hard windows on the start of service, full recharge by default.
- Event-driven multi-vehicle simulation, independent log replay, and dynamic releases that are not conditioned on an offline route.
- A small exhaustive reference for toy instances.

Parts 2 and 3 (robust certificates, self-triggered replanning, computation deadlines, large comparisons) are not implemented.

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
```

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
