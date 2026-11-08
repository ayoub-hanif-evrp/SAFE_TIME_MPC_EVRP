"""Versioned continuation certificates for event-aware M1 retention."""

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

    def compatible_anchors(self, observation: Observation) -> bool:
        if self.current is None:
            return False
        for vehicle in observation.vehicles:
            prev = self.current.anchors.get(vehicle.id)
            if prev is None:
                return False
            if prev.node != vehicle.anchor.node:
                return False
            if abs(prev.time - vehicle.anchor.time) > 1e-9:
                return False
            if abs(prev.soc - vehicle.anchor.soc) > 1e-9:
                return False
            if abs(prev.load - vehicle.anchor.load) > 1e-9:
                return False
            if set(prev.onboard) != set(vehicle.anchor.onboard):
                return False
        return True

    def advance_or_invalidate(self, observation: Observation) -> ContinuationCertificate | None:
        """Reuse certificate only when anchors match exactly; else invalidate.

        Completed services are dropped from the served set bookkeeping. Physical
        route suffixes are not blindly truncated without revalidation (caller must
        revalidate).
        """
        if self.current is None:
            return None
        completed = set(observation.completed) | set(observation.in_service)
        if self.compatible_anchors(observation):
            self.reuse_count += 1
            self.advance_count += 1
            remaining = tuple(c for c in self.current.served if c not in completed)
            self.current = ContinuationCertificate(
                version=self.current.version,
                routes={vid: list(vs) for vid, vs in self.current.routes.items()},
                served=remaining,
                anchors={v.id: v.anchor for v in observation.vehicles},
                accepted=frozenset(observation.accepted),
                assumptions=self.current.assumptions,
                notes=list(self.current.notes) + ["advanced_same_anchors"],
            )
            return self.current
        self.invalidate_count += 1
        self.current = None
        return None
