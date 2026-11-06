"""Certified backup. A staged candidate does not become the backup until commit."""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.robust.certificate import Certificate, Verdict


def active_visits(visits: list[Visit], observation: Observation) -> list[Visit]:
    """Drop service stops that are already finished or covered by the current action.

    The MPC plan is a suffix from the anchor. Completed and in-service customers are
    not future visits. The physical action already in progress is not restarted.
    """
    skip = set(observation.completed) | set(observation.in_service) | set(observation.rejected)
    return [visit for visit in visits if not (visit.purpose == "service" and visit.node_id in skip)]


def align_suffix(visits: list[Visit], observation: Observation, node: str) -> list[Visit]:
    """Keep the portion of a route that is still ahead of the vehicle.

    Completed services are behind the cursor. If the vehicle is already at a stop
    that is still required, the suffix starts at that stop. Earlier depot reloads
    and charges are not replayed.
    """
    done = set(observation.completed) | set(observation.in_service) | set(observation.rejected)
    cursor = 0
    for index, visit in enumerate(visits):
        if visit.purpose == "service" and visit.node_id in done:
            cursor = index + 1
            continue
        services_before = [item for item in visits[:index] if item.purpose == "service"]
        if services_before and any(item.node_id not in done for item in services_before):
            continue
        if visit.node_id == node:
            cursor = index
            break
    return visits[cursor:]


def dispatch_suffix(
    visits: list[Visit],
    observation: Observation,
    node: str,
    soc: float,
    battery_capacity: float,
) -> list[Visit]:
    """Align a route and skip a charge that the vehicle has already completed."""
    suffix = align_suffix(visits, observation, node)
    while suffix and suffix[0].purpose == "charge" and suffix[0].node_id == node:
        target = battery_capacity if suffix[0].charge_target is None else suffix[0].charge_target
        if soc + 1e-9 < target:
            break
        suffix = suffix[1:]
    return suffix


def action_id(observation: Observation) -> str:
    """Identity of the physical actions, excluding the idle clock."""
    parts: list[str] = []
    for vehicle in observation.vehicles:
        parts.append(
            "|".join(
                (
                    vehicle.id,
                    vehicle.status,
                    vehicle.node,
                    vehicle.locked_destination or "",
                    f"{vehicle.soc:.6f}",
                    f"{vehicle.load:.6f}",
                    ",".join(vehicle.onboard),
                )
            )
        )
    commitments = ",".join(observation.accepted)
    return f"{';'.join(parts)}#{commitments}"


def observation_version(observation: Observation, uncertainty=None) -> str:
    """Version covering physical state, request status and uncertainty hypotheses."""
    base = action_id(observation)
    requests = (
        f"open={','.join(observation.released_open)}"
        f"|acc={','.join(observation.accepted)}"
        f"|done={','.join(observation.completed)}"
        f"|rej={','.join(observation.rejected)}"
        f"|svc={','.join(observation.in_service)}"
        f"|def={','.join(observation.deferred)}"
    )
    if uncertainty is None:
        return f"{base}|{requests}"
    bounds = (
        f"t[{uncertainty.time_lower},{uncertainty.time_upper}]"
        f"e[{uncertainty.energy_lower},{uncertainty.energy_upper}]"
        f"floor={uncertainty.soc_floor}"
    )
    return f"{base}|{requests}|{bounds}"


@dataclass
class BackupStore:
    routes: dict[str, list[Visit]] = field(default_factory=dict)
    certificate: Certificate | None = None
    version: int = 0
    state_id: str = ""
    _staged_routes: dict[str, list[Visit]] | None = None
    _staged_certificate: Certificate | None = None
    _staged_state_id: str = ""

    def stage(self, routes: dict[str, list[Visit]], certificate: Certificate, state_id: str) -> bool:
        if certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
            return False
        self._staged_routes = {vid: list(visits) for vid, visits in routes.items()}
        self._staged_certificate = certificate
        self._staged_state_id = state_id
        return True

    def commit(self, state_id: str) -> bool:
        """Replace the backup only when the staged certificate still matches the state."""
        if self._staged_routes is None or self._staged_certificate is None:
            return False
        if state_id != self._staged_state_id:
            self.discard()
            return False
        if self._staged_certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
            self.discard()
            return False
        self.routes = self._staged_routes
        self.certificate = self._staged_certificate
        self.state_id = state_id
        self.version += 1
        self.discard()
        return True

    def discard(self) -> None:
        self._staged_routes = None
        self._staged_certificate = None
        self._staged_state_id = ""

    @property
    def certified(self) -> bool:
        return self.certificate is not None and self.certificate.verdict is Verdict.CERTIFIED_FEASIBLE
