# Generic finite-state dynamic EVRP model

Package: `src/safe_time_evrp/dr_dual/generic/`  
See also: `URGENT_CORRECTNESS_REPAIR.md` (Nov 2026 quarantine).

## Scope (not a continuous EVRP optimum)

Two reference solvers, with **explicit** status scope:

| Solver | Status when complete | Action / policy class |
|--------|----------------------|------------------------|
| `exact_dp.solve_generic_exact` | `EXACT_OPTIMUM_RESTRICTED` | First travel + short **common** continuation plans (max length / branching / plan caps); primary-vehicle-biased generation |
| `event_oracle.solve_event_exact` | `EXACT_OPTIMUM_FULL_FINITE` | Belief-state DP over `legal_fleet_actions` within depth/node limits |

Incomplete search → `FEASIBLE_INCUMBENT` | `UNKNOWN` | `TIME_LIMIT`.  
**Never** interpret a truncated empty search as `PROVEN_INFEASIBLE`.

## Dynamics (corrected)

1. **Announcement** at `metadata.announce_at` when `global_clock(state) ≥ release` (`release_due_announcements`).
2. **ACCEPT / REJECT** are fleet-level decisions after announcement — **not** tied to being at the customer node (`fleet_accept_actions`).
3. **Dispatch / TRAVEL / CHARGE / WAIT** per free vehicle; **SERVE** only at customer node if accepted.
4. **Episode complete** only if no pending future releases, all accepted customers completed, and depot-return contract (if any) holds.
5. Observations update shared belief **only** after completed travel (`apply_action`); history keys never include hidden θ.

## Components

| Module | Role |
|--------|------|
| `model.py` | Tiny networks (1–2 EVs, few customers, chargers) |
| `actions.py` | Global clock, releases, fleet ACCEPT, `episode_complete`, `legal_fleet_actions` |
| `history.py` | Observable history keys |
| `common_continuation.py` | Restricted common-plan search |
| `exact_dp.py` | Restricted finite policy-tree reference |
| `event_oracle.py` | Small belief-state fleet reference |
| `general_bound.py` | Quarantined TEI + trivial safe UB |
| `counterexamples.py` | Five-action multi-customer undercount |
| `closed_loop.py` | RH driver awaiting full episode lifecycle |
| `discriminating_suite.py` | D1–D4 development instances |
| `instance_gen.py` | Legacy frozen seeds (structural only; not behavioral scale evidence) |

## Architecture

Exact / event references use `WorldState` + `apply_action` + `DiscreteBelief`.  
`FleetSimulator` is **not** the exact plant. Closed-loop plant cross-check remains deferred until a repaired tight bound is sound **and** useful.

## Frozen A/C/S references

DRUB, REUB_v1, OTUB remain family-restricted baselines. No further A/C/S tightening in this cycle.
