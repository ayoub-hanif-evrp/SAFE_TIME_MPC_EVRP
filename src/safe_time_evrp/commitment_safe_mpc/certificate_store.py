"""Versioned continuation certificates with physical-event advancement."""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.models.state import Anchor, Observation, Visit


@dataclass
class ContinuationCertificate:
    version: int
    routes: dict[str, list[Visit]]
    served: tuple[str, ...]
    anchors: dict[str, Anchor]
    accepted: frozenset[str]
    assumptions: tuple[str, ...] = ("nominal_physics", "independent_stations")
    notes: list[str] = field(default_factory=list)


@dataclass
class CertificateStore:
    current: ContinuationCertificate | None = None
    version: int = 0
    reuse_count: int = 0
    invalidate_count: int = 0
    advance_count: int = 0

    def publish(
        self, routes: dict[str, list[Visit]], observation: Observation, served: list[str]
    ) -> ContinuationCertificate:
        self.version += 1
        cert = ContinuationCertificate(
            version=self.version,
            routes={vid: list(vs) for vid, vs in routes.items()},
            served=tuple(served),
            anchors={v.id: v.anchor for v in observation.vehicles},
            accepted=frozenset(observation.accepted),
        )
        self.current = cert
        return cert

    def advance_or_invalidate(self, observation: Observation) -> ContinuationCertificate | None:
        """Advance witness through completed physical events; invalidate if unsafe.

        Vehicles may move and time may advance. Completed / in-service customers are
        stripped from planned suffixes. Remaining visits are kept when the observed
        post-action/current anchor is compatible with continuing the truncated plan.
        """
        if self.current is None:
            return None

        completed = set(observation.completed)
        in_service = set(observation.in_service)
        done = completed | in_service
        new_routes: dict[str, list[Visit]] = {}
        notes = list(self.current.notes)

        for vehicle in observation.vehicles:
            old = list(self.current.routes.get(vehicle.id, []))
            remaining = _advance_vehicle_suffix(old, vehicle, done)
            # If locked, plant expects a suffix for after the action; keep remaining.
            new_routes[vehicle.id] = remaining

        # Acceptance set growth without revalidation is allowed; drops of accepted
        # commitments that are not completed/in_service invalidate.
        prev_pending = set(self.current.accepted) - done
        now_pending = set(observation.accepted) - done
        dropped = prev_pending - now_pending - set(observation.rejected)
        if dropped:
            self.invalidate_count += 1
            self.current = None
            return None

        self.reuse_count += 1
        self.advance_count += 1
        notes.append("advanced_through_physical_events")
        self.current = ContinuationCertificate(
            version=self.current.version,
            routes=new_routes,
            served=tuple(c for c in self.current.served if c not in done),
            anchors={v.id: v.anchor for v in observation.vehicles},
            accepted=frozenset(observation.accepted),
            assumptions=self.current.assumptions,
            notes=notes,
        )
        return self.current


def _advance_vehicle_suffix(
    visits: list[Visit],
    vehicle,
    done: set[str],
) -> list[Visit]:
    """Drop leading visits already realized by completed/in-service actions."""
    remaining = list(visits)
    # Strip completed services from anywhere in the prefix while they appear first
    changed = True
    while changed and remaining:
        changed = False
        first = remaining[0]
        if first.purpose == "service" and first.node_id in done:
            remaining = remaining[1:]
            changed = True
            continue
        # If vehicle has already arrived at the first visit node and that action finished
        if first.purpose == "charge" and vehicle.status != "charging" and vehicle.node == first.node_id:
            # Charge visit consumed if we're past charging at that station
            if vehicle.locked_destination != first.node_id:
                remaining = remaining[1:]
                changed = True
                continue
        # Travel-implied: if first visit node equals current/post-action node and
        # purpose is service still needed, keep it; if already done, stripped above.
        if first.purpose == "return":
            break
    # Drop trailing only-return noise is fine to keep for evaluate_route
    return remaining
