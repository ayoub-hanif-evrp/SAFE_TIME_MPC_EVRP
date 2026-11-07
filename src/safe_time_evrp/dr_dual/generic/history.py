"""Observable history keys for nonanticipative policies."""

from __future__ import annotations

from safe_time_evrp.dr_dual.state import WorldState


def history_key(state: WorldState) -> tuple:
    """Controller-visible fingerprint (never includes θ)."""
    vehicles = tuple(
        (v.vehicle_id, v.node, round(v.time, 3), round(v.soc, 3), round(v.load, 3)) for v in state.vehicles
    )
    return (
        vehicles,
        tuple(sorted(state.accepted)),
        tuple(sorted(state.completed)),
        tuple(sorted(state.announced)),
        tuple(sorted(state.belief.support_set())),
        state.model_inconsistent,
    )
