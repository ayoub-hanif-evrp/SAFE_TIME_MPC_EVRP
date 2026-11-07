# Baseline comparison

```bash
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; write_artifacts(Path('docs/decision_relevant_dual_mpc'))"
python -m safe_time_evrp.dr_dual.compute_study
```

## Selection criteria (separated)

| Method | Optimizes |
|--------|-----------|
| Exact / pruned dual | Bayes + nonanticipative continuations |
| Robust MPC | Worst-case, forced prior |
| Optimized passive | Forced-prior expected continuation |
| Info-gain heuristic | Max \|φ₁\| among safe |

Report both selection score and true Bayes value of the chosen first action.

## Suite note

On several toys, info-gain already matches the exact first action — that is recorded, not hidden. A methodological contribution cannot rest on beating a weak baseline by construction.

## Compute

Unpruned search computes **no** unused bounds. Compare expansions, bound-construction overhead, and total heavy ops across the preregistered suite (`GENERALIZATION_RESULTS.md`). Millisecond means on 3–5 trials are not scalability evidence.
