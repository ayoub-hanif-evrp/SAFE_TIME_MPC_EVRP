# Repository cleanup report

**Date:** 2026-11-14  
**Task:** Maintenance-only consolidation onto `main` (no methodology change).

## 1. Branch counts

| Stage | Remote branches | Local branches |
|-------|-----------------|----------------|
| Pre-cleanup | 12 (`main` + 11 `research/*`) | `main` + research tips |
| After obsolete-gate deletion | 2 (`main`, `research/commitment-safe-predictive-mpc`) | same |
| **Final** | **1 (`main`)** | **1 (`main`)** |

## 2. Branches deleted

Verified as ancestors of research HEAD `a0cb460` before deletion:

1. `research/causal-mpc-validation`
2. `research/closedloop-repair-gate`
3. `research/commitment-cost-mpc-gate`
4. `research/decision-mpc-gate`
5. `research/decision-relevant-dual-mpc`
6. `research/experimental-validity-gate`
7. `research/multistage-viability-gate`
8. `research/realdata-mpc-gate`
9. `research/safe-dual-mpc`

10. `research/commitment-safe-predictive-mpc` (local + `origin`) — deleted after CI green on cleanup commit `6799141`

**Never deleted:** `main`.

## 3. Recovery tag

| Field | Value |
|-------|--------|
| Name | `archive/pre-repository-cleanup-2026-11-14` |
| Annotated tag object | `5dad91bda37bc41f842c15ce194250a71c9cdeae` |
| Peels to commit | `a0cb460b3bef26a40d22ac53dff2150ef0a5548d` |
| Message | Pre-repository-cleanup recovery snapshot … INCREMENTAL_RESULT |

Restore:

```bash
git fetch origin tag archive/pre-repository-cleanup-2026-11-14
git checkout archive/pre-repository-cleanup-2026-11-14
```

## 4. Files / folders removed or consolidated

### Consolidated (moved)

- Final formulation → `docs/methodology/`
- Certificate proof → `docs/proofs/`
- Frozen holdout, Phase 3E/3F, final experiment artifacts → `docs/experiments/`
- Reproducibility manifest → `docs/reproducibility/`

### Removed from working tree (history retained on recovery tag)

- `docs/commitment_safe_mpc/*.md` narratives (JSON compatibility artifacts retained)
- `docs/decision_relevant_dual_mpc/`
- `docs/safe_dual_mpc/`
- `docs/part2_5/`
- `docs/research_gate_3a` … `docs/research_gate_4`
- Superseded narrative MD under `docs/mpc_central/` (accelerated / Phase 3B–D gate reports, older formulation drafts)

### Added

- `docs/mpc_central/README.md` (pointer)
- `docs/reproducibility/RESEARCH_HISTORY.md`
- `docs/reproducibility/REPOSITORY_FILE_MANIFEST.md`
- `docs/reproducibility/REPOSITORY_CLEANUP_REPORT.md`
- Rewritten root `README.md`
- `.gitignore` scratch-inventory patterns

### Code path defaults (behavior-preserving)

- `publication_closeout.py` / `final_mpc_package.py` write under `docs/experiments/` and `docs/reproducibility/` instead of `docs/mpc_central/`.

## 5. Deliberately preserved

- CC-E-MPC, CertificateStore, M1/B1, ALNS, plant, replay, forecasts  
- Frozen holdout JSON and negative / incremental findings  
- Phase 3E/3F evidence (fairness + switching REVISE)  
- Manuscript + readiness (`INCREMENTAL_RESULT`)  
- Conditional certificate proof and limitations  
- Compatibility JSON under `docs/mpc_central/` required by unit tests  
- `dr_dual` / `part2*` / switching MPC modules still imported by tests  

## 6. Tracked-file counts

| Stage | Tracked files |
|-------|---------------|
| Pre-cleanup (`a0cb460`) | **390** |
| Post-cleanup (this commit) | **276** |

## 7. Tests and CI

| Check | Pre-cleanup | Post-cleanup |
|-------|-------------|--------------|
| Ruff | pass | pass (`ruff check` + format check) |
| Pytest collect | 278 | 278 |
| Pytest full | pass at `a0cb460` | **278 passed** (post-reorg worktree) |
| CI on `main` | green run `43635807536` at `a0cb460` | **green** run [`43636791333`](https://github.com/ayoub-hanif-evrp/SAFE_TIME_MPC_EVRP/actions/runs/43636791333) at `6799141` |

## 8. Unresolved blockers / CI note

Recovery tag verified (peels to `a0cb460`; e.g. `docs/research_gate_3e/RESEARCH_DECISION.md` still listed on the tag tree). Only remote branch remaining: `origin/main`.

Cleanup commit `6799141` had green CI with successful public-benchmark download. Later docs-only pushes intermittently hit external-host download failures; `test_benchmark_data` then failed hard. Mitigation (maintenance only): skip that test when archives are absent, and stop failing the whole CI job solely because the optional public download soft-failed.
