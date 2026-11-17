# SAFE_TIME_MPC_EVRP

Commitment-safe stochastic **MPC** for dynamic electric vehicle routing (EVRPTW): irreversible accepts, battery and time windows, nonlinear charging, certified emission.

**Primary method:** commitment-safe stochastic MPC with SPI-over-greedy selection.  
**Paper stance:** non-inferiority vs strong economic MPC + nonlinear charging mechanism (not blanket \(J\) dominance / recursive feasibility).

## Install

Python 3.11+.

```bash
pip install -e ".[dev]"
python -m safe_time_evrp.data.download   # optional public benchmarks
python -m safe_time_evrp.data.verify
```

Benchmark archives stay under `data/raw/` (gitignored). Provenance: [`docs/datasets/DATA_PROVENANCE.md`](docs/datasets/DATA_PROVENANCE.md). Active datasets: [`data/ACTIVE_DATASETS.json`](data/ACTIVE_DATASETS.json).

## Tests

```bash
python -m ruff check src tests
python -m ruff format --check src tests
python -m pytest -q
```

## Reproduce paper evaluation

```bash
python -m safe_time_evrp.mpc_central.mpc_paper_eval
```

Results:

- [`docs/experiments/MPC_PAPER_EVAL_RESULTS.md`](docs/experiments/MPC_PAPER_EVAL_RESULTS.md)
- [`docs/experiments/MPC_HOMBERGER_LATENCY.md`](docs/experiments/MPC_HOMBERGER_LATENCY.md)
- [`docs/experiments/MPC_NONLINEAR_EV_ABLATION.md`](docs/experiments/MPC_NONLINEAR_EV_ABLATION.md)

## Documentation (minimal)

| Path | Contents |
|------|----------|
| [`docs/methodology/COMMITMENT_SAFE_STOCHASTIC_MPC.md`](docs/methodology/COMMITMENT_SAFE_STOCHASTIC_MPC.md) | Method formulation |
| [`docs/methodology/PUBLIC_INFORMATION_CONTRACT.md`](docs/methodology/PUBLIC_INFORMATION_CONTRACT.md) | Public-info contract |
| [`docs/formulation/PROBLEM_DEFINITION.md`](docs/formulation/PROBLEM_DEFINITION.md) | Plant / problem |
| [`docs/research/MPC_RESEARCH_DECISION_MEMO.md`](docs/research/MPC_RESEARCH_DECISION_MEMO.md) | Locked research decision |
| [`docs/paper/MPC_TOP_TIER_READINESS.md`](docs/paper/MPC_TOP_TIER_READINESS.md) | Readiness / claim scope |
| [`docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`](docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md) | RF withdrawn; emission soundness |
| [`docs/datasets/DATA_PROVENANCE.md`](docs/datasets/DATA_PROVENANCE.md) | Data provenance |

## Licence / data

Do not commit raw benchmark blobs. See `docs/datasets/DATA_PROVENANCE.md`.
