# Generic finite-state dynamic EVRP model

Package: `src/safe_time_evrp/dr_dual/generic/`

## Scope (not a continuous EVRP optimum)

`EXACT_OPTIMUM` means optimal within:

1. Finite first-action travel set from the primary free vehicle.
2. Short common continuation plans (max length / branching caps) that are **nonanticipative** (one plan for an ambiguous posterior support).
3. Explicit depot-return contract when `metadata.require_depot_return` is true.
4. Customer announcements via `metadata.announce_at` released by fleet clock.

## Components

| Module | Role |
|--------|------|
| `model.py` | 1–2 EVs, 3–5 customers, corridors, chargers |
| `actions.py` | Legal atomic actions + announcement release + clock sync |
| `history.py` | Observable history keys |
| `common_continuation.py` | Generic common-plan search |
| `exact_dp.py` | Finite policy-tree exact reference |
| `general_bound.py` | Generic TEI resource UB |
| `closed_loop.py` | Receding-horizon with carried `WorldState` |
| `instance_gen.py` | Frozen seeds for scaling study |

## Architecture

Exact DP uses `WorldState` + `apply_action` + `DiscreteBelief`.  
`FleetSimulator` is **not** the exact plant (no belief / immutable branch). Closed-loop cross-check against FleetSimulator is deferred until the generic bound is sound and useful.

## Frozen A/C/S references

DRUB, REUB_v1, OTUB remain as family-restricted baselines. No further A/C/S tightening in this cycle.
