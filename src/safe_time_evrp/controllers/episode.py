"""Closed-loop coupling of the event simulator and the MPC baseline.

Optimization time is the sum of ``Decision.optimize_seconds``. Simulation time is
the wall clock spent outside those calls. Neither quantity is a hard process-level
timeout guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, LogRecord

_TRIGGERS = {
    "request_release",
    "arrive",
    "service_end",
    "charge_end",
    "wait_end",
    "replan_interval",
}


@dataclass
class EpisodeResult:
    log: list[LogRecord]
    decisions: list[Decision]
    optimize_seconds: float
    simulation_seconds: float
    final_requests: dict[str, str]
    release_times: dict[str, float]
    no_feasible_continuation_count: int
    fallback_count: int
    horizon_extended_count: int
    termination_reason: str = "unspecified"
    pending_next_event_time: float | None = None
    t_max: float | None = None


def run_episode(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
    horizon: float,
    max_replan_interval: float,
    t_max: float,
    energy: NominalLinearEnergy | None = None,
    max_events: int = 20_000,
    controller=None,
) -> EpisodeResult:
    if max_replan_interval <= 0:
        raise ValueError("replanning interval must be positive")
    model = energy or NominalLinearEnergy()
    simulator = FleetSimulator(instance, fleet_size, model)
    for customer_id, release_time in releases:
        simulator.schedule_release(customer_id, release_time)
    if controller is None:
        controller = EventTriggeredMPC(instance, horizon, model)
    decisions: list[Decision] = []
    optimize_seconds = 0.0
    simulation_seconds = 0.0
    replan_id: int | None = None
    same_time = 0
    last_decision_time = -1.0

    def decide(trigger: str) -> None:
        nonlocal optimize_seconds, replan_id, same_time, last_decision_time
        if abs(simulator.time - last_decision_time) <= EPS:
            same_time += 1
        else:
            same_time = 0
            last_decision_time = simulator.time
        if same_time > 32:
            raise RuntimeError("decision loop did not advance time")
        decision = controller.decide(simulator.observation(), trigger)
        optimize_seconds += decision.optimize_seconds
        decisions.append(decision)
        simulator.apply_decision(decision)
        if replan_id is not None:
            simulator.cancel(replan_id)
        replan_id = simulator.schedule_replan(simulator.time + max_replan_interval)

    wall = perf_counter()
    if simulator.next_event_time() is None or simulator.next_event_time() > EPS:
        decide("initial")
    events = 0
    termination_reason = "unspecified"
    pending_next: float | None = None
    while events < max_events:
        nxt = simulator.next_event_time()
        pending_next = nxt
        if nxt is None:
            termination_reason = "no_pending_events"
            break
        if nxt > t_max + EPS:
            termination_reason = "cutoff_next_event_after_tmax"
            break
        event = simulator.pop_event()
        events += 1
        if event is None:
            termination_reason = "pop_returned_none"
            break
        if event.kind in _TRIGGERS:
            decide(event.kind)
        if _finished(simulator, t_max):
            termination_reason = "natural_completion"
            pending_next = simulator.next_event_time()
            break
    else:
        raise RuntimeError("event limit reached before the episode finished")
    if termination_reason == "unspecified":
        termination_reason = "loop_exit_unspecified"
    simulator.mark_finished()
    total = perf_counter() - wall
    simulation_seconds = max(0.0, total - optimize_seconds)
    return EpisodeResult(
        log=simulator.log,
        decisions=decisions,
        optimize_seconds=optimize_seconds,
        simulation_seconds=max(0.0, simulation_seconds),
        final_requests={cid: status.value for cid, status in simulator.requests.items()},
        release_times=dict(simulator.release_time),
        no_feasible_continuation_count=sum(d.no_feasible_continuation for d in decisions),
        fallback_count=sum(d.fallback_used for d in decisions),
        horizon_extended_count=sum(d.horizon_extended for d in decisions),
        termination_reason=termination_reason,
        pending_next_event_time=pending_next,
        t_max=t_max,
    )


def _finished(simulator: FleetSimulator, t_max: float) -> bool:
    del t_max
    open_status = {"announced", "accepted", "deferred", "in_service"}
    if any(status.value in open_status for status in simulator.requests.values()):
        return False
    if any(simulator.requests[cid].value == "hidden" for cid in simulator.release_time):
        return False
    depot = simulator.instance.depot_id
    for vehicle in simulator.vehicles.values():
        if vehicle.status.value != "idle" or vehicle.node != depot:
            return False
    return True
