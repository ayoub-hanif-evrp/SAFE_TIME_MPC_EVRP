# Physical contract (Phase B target)

Status: **stub — authoritative plant unification is the next milestone.**

## Required semantics

1. Multi-EV positions, SOC, load, busy/noninterruptible activity  
2. Time-stamped customer announcements  
3. Separate announce / accept / assign / dispatch / serve-complete  
4. Hard time windows  
5. Travel time and energy  
6. Charging per declared model  
7. Noninterruptible physical actions  
8. Depot return / terminal rules  
9. One global chronological event queue  
10. Replan only on observable events  

Controllers must never observe hidden future request identities or release times. Accepted commitments ≠ provisional route assignments.

## Current SAFE_TIME plant pieces

- `dr_dual/transition.py` + `WorldState` (atomic actions used by restricted oracle)  
- `dr_dual/replay.py` (independent first-travel / log checks)  
- `dr_dual/generic/actions.py` (`global_clock`, fleet ACCEPT, `episode_complete`)  

## Reference (adapt, do not merge)

`MPC_EVRP`: `evrp/simulator.py`, `observation.py`, `mpc.py`, `research_v3a/simulator.py`, `research_v3a/replay.py`

Phase B will select the most reliable SAFE_TIME event plant and fill gaps from MPC_EVRP only where demonstrated.
