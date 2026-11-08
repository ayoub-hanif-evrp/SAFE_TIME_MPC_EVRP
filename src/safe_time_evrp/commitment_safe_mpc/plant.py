"""Authoritative physical plant for commitment-safe MPC (Phase B).

The research controllers (B0/B1/M1) must couple to this plant only. The ``dr_dual``
atomic transition model remains a verification/oracle sandbox, not the fleet plant.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, LogRecord, Observation
from safe_time_evrp.validation.replay import ReplayReport, validate_log

AUTHORITATIVE_PLANT = "safe_time_evrp.environment.simulator.FleetSimulator"
AUTHORITATIVE_REPLAY = "safe_time_evrp.validation.replay.validate_log"


@dataclass(frozen=True)
class AuthoritativePlant:
    """Thin facade documenting the single plant/replay contract."""

    simulator_cls: type = FleetSimulator
    replay = staticmethod(validate_log)
    run_closed_loop = staticmethod(run_episode)

    def name(self) -> str:
        return AUTHORITATIVE_PLANT


def make_simulator(instance: Instance, fleet_size: int) -> FleetSimulator:
    return FleetSimulator(instance, fleet_size)


def verify_episode_log(instance: Instance, log: list[LogRecord], **kwargs) -> ReplayReport:
    return validate_log(instance, log, **kwargs)


def observation_hides_future(obs: Observation) -> bool:
    """Structural check: Observation type has no hidden-future customer field."""
    return "hidden" not in type(obs).__dataclass_fields__  # type: ignore[attr-defined]


def decision_preserves_locked(decision: Decision, observation: Observation) -> bool:
    for vehicle in observation.vehicles:
        if vehicle.locked_destination is None:
            continue
        if decision.locked_destinations.get(vehicle.id) != vehicle.locked_destination:
            return False
    return True
