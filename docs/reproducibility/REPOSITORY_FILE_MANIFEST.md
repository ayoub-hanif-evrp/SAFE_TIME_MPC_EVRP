# Repository file manifest (post-cleanup)

**Recovery tag:** `archive/pre-repository-cleanup-2026-11-14` → commit `a0cb460b3bef26a40d22ac53dff2150ef0a5548d`  
**Branch:** `main`  
**Pre-cleanup tracked files:** 390  
**Classification policy:** KEEP by default when used by controllers, tests, CI, frozen results, or manuscript; REMOVE FROM WORKING TREE only when superseded narrative/JSON and recoverable from the tag; REVIEW left in tree.

## Top-level layout

| Path | Class | Role |
|------|-------|------|
| `README.md` | KEEP | Project entry documentation |
| `pyproject.toml` | KEEP | Package / tool config |
| `.gitignore` | KEEP | Ignore caches, raw data, plots |
| `.github/` | KEEP | CI workflows |
| `configs/` | KEEP | Experiment configs |
| `data/` | KEEP | Manifests / provenance hooks (raw blobs gitignored) |
| `docs/` | KEEP | Scientific documentation (see below) |
| `scripts/` | KEEP | Utility entry scripts |
| `src/safe_time_evrp/` | KEEP | Implementation packages |
| `tests/` | KEEP | Automated tests |
| `experiments/` | KEEP | Development experiment hooks (outputs gitignored) |

## `docs/`

| Path | Class | Role |
|------|-------|------|
| `docs/methodology/` | KEEP | Final CC-E-MPC formulation |
| `docs/proofs/` | KEEP | Conditional certificate proposition |
| `docs/experiments/` | KEEP | Phase 3E/3F + final/frozen numerical artifacts |
| `docs/paper/` | KEEP | Manuscript + readiness (`INCREMENTAL_RESULT`) |
| `docs/reproducibility/` | KEEP | Manifest, cleanup report, history |
| `docs/formulation/` | KEEP | Plant / physics formulation |
| `docs/validation/` | KEEP | Validation contracts |
| `docs/datasets/` | KEEP | Data provenance / licences |
| `docs/literature/` | KEEP | Prior-art notes retained for context |
| `docs/part2/` | KEEP | Part-2 certificate lineage still referenced by code/tests |
| `docs/mpc_central/` | KEEP / CONSOLIDATE | Compatibility JSON for historical gates + tests; README pointer |

### Removed from working tree (recover from tag)

Entire superseded narrative trees (examples):

- `docs/commitment_safe_mpc/` narratives (JSON compatibility artifacts + README retained)
- `docs/decision_relevant_dual_mpc/`
- `docs/safe_dual_mpc/`
- `docs/part2_5/`
- `docs/research_gate_3a` … `docs/research_gate_4`
- Superseded `docs/mpc_central/*.md` audits (ACCELERATED_*, PHASE3B–D narratives, etc.)

**Deliberately preserved numerical evidence** (moved under `docs/experiments/`): frozen holdout, Phase 3E/3F JSON/MD, final development results, certificate audit.

## `src/safe_time_evrp/`

| Package | Class | Role |
|---------|-------|------|
| `mpc_central/` | KEEP | CC-E-MPC, closeout, Phase 3E/3F, plant helpers |
| `commitment_safe_mpc/` | KEEP | B1, M1, ALNS, certificate store, predictive MPC |
| `controllers/`, `plant/`, `physics/`, `alns/`, `forecast/`, `evaluation/`, `data/` | KEEP | Core runtime |
| `dr_dual/`, `part2/`, `part2_5/` | REVIEW / KEEP | Historical modules still imported by tests and residual experiments — not deleted |
| `safe_dual_mpc/` (if present) | REVIEW | Retained while tests reference dual lineage |

No controller scientific behavior changed during cleanup (path defaults for artifact writers only).

## Tests / CI

All `tests/*.py` kept. CI workflows under `.github/` unchanged in intent. Artifact write defaults for closeout/final package now target `docs/experiments/` and `docs/reproducibility/`.
