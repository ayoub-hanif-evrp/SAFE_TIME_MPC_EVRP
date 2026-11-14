# Schneider-derived dynamic EVRPTW protocol

**Label:** Schneider-derived dynamic EVRPTW  
**Protocol version:** `2026-11-14.v1`  
**Static deposit:** Goeke E-VRPTW / Schneider–Stenger–Goeke, Mendeley Data DOI [10.17632/h3mrm5dhxw.1](https://doi.org/10.17632/h3mrm5dhxw.1)

## What is preserved

From each Schneider file we keep unchanged:

- customer coordinates, demands, service times, time windows  
- charger locations  
- depot and vehicle parameters \(Q, C, r, g, v\)  
- Euclidean distance / travel-time / energy definitions from the deposited readme  

We do **not** claim these are the original static Schneider experiments. Controllers are evaluated on **derived** online announcement times.

## What is added

Stochastic customer-announcement times (`environment_seed` only):

1. Shuffle customers with a deterministic LCG seeded by `environment_seed`.  
2. Mark the first \(\lfloor f \cdot n \rfloor\) as **known at \(t=0\)** (fraction \(f\) from the dynamicity table).  
3. Draw successive exponential interarrivals for the remaining customers with mean  
   \(\mu = \texttt{mean\_interarrival\_scale} \cdot H / n\), where \(H\) is the depot/customer due horizon.  
4. Clamp each dynamic announcement to  
   \(t \le \max(0,\; \texttt{due} - \texttt{service} - \texttt{travel}(\texttt{depot},\texttt{customer}))\).  

Windows and energy limits are **not** relaxed. Controllers never observe unreleased customers.

### Dynamicity (preregistered)

| Level | Known fraction | Interarrival scale |
|-------|----------------|--------------------|
| low | 0.60 | 0.22 |
| medium | 0.30 | 0.12 |
| high | 0.10 | 0.06 |

Main reported table uses **medium** unless otherwise stated.

## Fleet size rule

\[
\texttt{fleet} = \min\bigl(6,\ \max(\lceil D/C \rceil,\ \lceil n/5 \rceil)\bigr)
\]

Recorded on every episode (`fleet_rule` field). Capacities are not inflated.

## Seed semantics

| Seed | Controls |
|------|----------|
| `environment_seed` | Announcement realization only |
| `policy_seed` | Controller / ALNS / forecast RNG |

For a fixed instance and realization index, **all paired controllers share the same releases and the same policy seed**. Different environment seeds must change the release schedule whenever the generator can vary.

## Splits (by base instance)

Among the **36** Schneider files with 5/10/15 customers, each \((\texttt{family},\texttt{size})\) stratum of four alphabetical stems is assigned:

- index 0 → **train** (forecast atoms only)  
- index 1 → **development**  
- indices 2–3 → **test**  

Machine-readable copy: `docs/reproducibility/DYNAMIC_BENCHMARK_MANIFEST.json`.

## Evaluation budget

Matched to the synthetic closeout package (not retuned on Schneider scores):

- ALNS iterations = 10, time limit = 0.35 s  
- forecast scenarios = 2  
- controllers: B1, M1, stochastic MPC, CC-E-MPC, CC-E-MPC without forecasts  

## Tiers

| Tier | Coverage |
|------|----------|
| `smoke` | `c101C5`, `r201C10`, `rc202C15` × 2 env realizations |
| `small` | all 36 small instances × 5 env realizations |
| `scale` | predeclared `c101_21`, `r101_21`, `rc101_21` × 1 env realization |

## Preconditions

Benchmark execution **must fail clearly** if the Schneider archive is missing or SHA-256 mismatched (`require_verified_schneider_archive`).

## Prior synthetic holdout

`B_adversarial_overaccept` was already evaluated in the publication closeout. It is **not** fresh unseen validation for this Schneider study.

## Runner

```bash
python -m safe_time_evrp.mpc_central.schneider_dynamic_eval --tier smoke
python -m safe_time_evrp.mpc_central.schneider_dynamic_eval --tier small
python -m safe_time_evrp.mpc_central.schneider_dynamic_eval --tier scale
```
