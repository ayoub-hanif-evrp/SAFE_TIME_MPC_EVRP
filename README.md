# SAFE_TIME_MPC_EVRP

Feasibility-preserving, computation-aware **model predictive control** for the dynamic electric vehicle routing problem (EVRP), with irreversible customer acceptances, battery and time-window constraints, and an ALNS route engine used as an internal optimizer.

**Primary branch:** `main`  
**Scientific assessment (honest):** incremental certificate-aware economic MPC synthesis — **not** demonstrated top-tier predictive superiority.

## What this repository implements

| Component | Role |
|-----------|------|
| **CC-E-MPC** (`CertificateCarryingEconomicMpc`) | Hard nominal commitment feasibility + expected-value ranking of first actions + persistent certificate fallback |
| **B1** | Reactive full-validation ALNS–MPC baseline |
| **M1** | Certificate-carrying ALNS (same `CertificateStore` family; no forecast EV ranking) |
| **Stochastic MPC** | Counterfactual expected-value MPC without the full persistent-store closeout path |
| Plant + replay | Event-driven multi-vehicle simulator and independent log validation |
| Forecasts | Train-only anonymous arrival scenarios (holdout frozen until closeout) |

**Limitations.** Certificate persistence is largely shared with M1 and did not improve completed-service counts vs “certificate off” when forecast scoring was on (9/9 ties). Development gains vs B1 are mixed; the frozen holdout tied B1/M1/stochastic MPC. See the manuscript and readiness report.

## Install

Python 3.11+.

```bash
pip install -e ".[dev]"
python -m safe_time_evrp.data.download   # optional public benchmarks
python -m safe_time_evrp.data.verify
```

Benchmark archives stay under `data/raw/` (gitignored). Provenance: `docs/datasets/DATA_PROVENANCE.md`.

## Tests and lint

```bash
python -m ruff check src tests
python -m ruff format --check src tests
python -m pytest -q
python -m safe_time_evrp.evaluation.smoke_test
```

## Reproduce final experiments

Frozen protocol and seeds: [`docs/reproducibility/REPRODUCIBILITY_MANIFEST.json`](docs/reproducibility/REPRODUCIBILITY_MANIFEST.json)

```bash
python -m safe_time_evrp.mpc_central.publication_closeout
python -m safe_time_evrp.mpc_central.final_mpc_package
```

Authoritative numerical artifacts: [`docs/experiments/`](docs/experiments/) (including `FROZEN_HOLDOUT_RESULTS.json` and `final_development_results.json`).

## Documentation map

| Path | Contents |
|------|----------|
| [`docs/methodology/FINAL_MPC_FORMULATION.md`](docs/methodology/FINAL_MPC_FORMULATION.md) | CC-E-MPC control law |
| [`docs/proofs/CERTIFICATE_FEASIBILITY_PROOF.md`](docs/proofs/CERTIFICATE_FEASIBILITY_PROOF.md) | Conditional certificate proposition |
| [`docs/experiments/`](docs/experiments/) | Audits, Phase 3E/3F evidence, frozen holdout |
| [`docs/paper/MPC_MANUSCRIPT_FINAL_DRAFT.md`](docs/paper/MPC_MANUSCRIPT_FINAL_DRAFT.md) | Manuscript draft |
| [`docs/paper/PUBLICATION_READINESS_REPORT.md`](docs/paper/PUBLICATION_READINESS_REPORT.md) | `INCREMENTAL_RESULT` decision |
| [`docs/reproducibility/`](docs/reproducibility/) | Cleanup report, file manifest, research history |
| [`docs/formulation/`](docs/formulation/), [`docs/validation/`](docs/validation/), [`docs/datasets/`](docs/datasets/) | Plant, validation, data licences |
| [`docs/mpc_central/`](docs/mpc_central/) | Compatibility JSON outputs for gate/tests |
| [`docs/commitment_safe_mpc/`](docs/commitment_safe_mpc/) | Frozen B1/M1 JSON artifacts still read by tests |

## Recovering the pre-cleanup archive

Full historical experiment trees and superseded research-gate docs are preserved on the annotated tag:

```bash
git fetch origin tag archive/pre-repository-cleanup-2026-11-14
git checkout archive/pre-repository-cleanup-2026-11-14
```

SHA: `a0cb460b3bef26a40d22ac53dff2150ef0a5548d`  
See [`docs/reproducibility/RESEARCH_HISTORY.md`](docs/reproducibility/RESEARCH_HISTORY.md).

## Licence / data

Schneider EVRP instances and other deposits: see `docs/datasets/DATA_PROVENANCE.md`. Do not commit raw benchmark blobs.
