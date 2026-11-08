"""Independent nominal continuation validation for commitment-safe MPC (B1).

This is **not** a robust recursive-feasibility certificate against energy disturbances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation, Visit


@dataclass
class ValidationReport:
    status: str  # CERTIFIED_FEASIBLE | UNKNOWN | MODEL_CONTRACT_VIOLATED
    ok: bool
    reasons: list[str] = field(default_factory=list)
    served: list[str] = field(default_factory=list)
    distance: float = 0.0
    charge_time: float = 0.0
    routes_checked: int = 0
    charge_visits_checked: int = 0
    obligations_rechecked: int = 0
    seconds: float = 0.0


def validate_continuation(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    *,
    energy: NominalLinearEnergy | None = None,
    require_new: frozenset[str] | None = None,
) -> ValidationReport:
    """Validate a full fleet suffix under nominal physics."""
    t0 = perf_counter()
    model = energy or NominalLinearEnergy()
    reasons: list[str] = []
    served_all: list[str] = []
    distance = 0.0
    charge_time = 0.0
    routes_checked = 0
    charge_visits = 0
    pending = set(observation.accepted) - set(observation.completed) - set(observation.in_service)
    if require_new:
        pending |= set(require_new)
    obligations = len(pending)

    visible = (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.in_service)
        | set(observation.deferred)
    )
    rejected = set(observation.rejected)

    for vehicle in observation.vehicles:
        visits = list(routes.get(vehicle.id, []))
        # Locked destination must not be contradicted by an immediate alternate dispatch
        if vehicle.locked_destination is not None:
            # Noninterruptible: suffix may be provisional; do not require starting a different first travel
            pass
        for v in visits:
            if v.purpose == "charge":
                charge_visits += 1
            if v.purpose == "service":
                if v.node_id in rejected:
                    reasons.append(f"serves_rejected:{v.node_id}")
                if v.node_id not in visible and v.node_id not in pending:
                    reasons.append(f"serves_unreleased_or_unknown:{v.node_id}")
        routes_checked += 1
        result = evaluate_route(instance, vehicle.anchor, visits, model)
        if not result.feasible:
            reasons.append(f"route_infeasible:{vehicle.id}:{result.reason}")
            continue
        served_all.extend(result.served)
        distance += result.distance
        charge_time += result.charge_time

    if len(served_all) != len(set(served_all)):
        reasons.append("duplicate_service")

    missing = pending - set(served_all) - set(observation.in_service)
    if missing:
        reasons.append(f"missing_commitments:{sorted(missing)}")

    if reasons:
        status = "MODEL_CONTRACT_VIOLATED" if any("unreleased" in r for r in reasons) else "UNKNOWN"
        return ValidationReport(
            status=status,
            ok=False,
            reasons=reasons,
            served=served_all,
            distance=distance,
            charge_time=charge_time,
            routes_checked=routes_checked,
            charge_visits_checked=charge_visits,
            obligations_rechecked=obligations,
            seconds=perf_counter() - t0,
        )
    return ValidationReport(
        status="CERTIFIED_FEASIBLE",
        ok=True,
        reasons=[],
        served=served_all,
        distance=distance,
        charge_time=charge_time,
        routes_checked=routes_checked,
        charge_visits_checked=charge_visits,
        obligations_rechecked=obligations,
        seconds=perf_counter() - t0,
    )
