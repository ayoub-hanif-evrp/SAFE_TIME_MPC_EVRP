"""Closed loop with an explicit compute-time model.

Wall-clock solver time is plant time. A candidate is committed only when no
physical event falls inside that interval and the certificate still holds at the
later clock. Otherwise the previous backup is executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision
from safe_time_evrp.robust.backup import action_id
from safe_time_evrp.robust.controller import SafeTimeController

_TRIGGERS = {
    "request_release",
    "arrive",
    "service_end",
    "charge_end",
    "wait_end",
    "replan_interval",
    "bound_update",
    "soc_discrepancy",
    "disruption",
}


@dataclass
class RobustEpisode:
    decisions: list[Decision]
    final_requests: dict[str, str]
    optimize_count: int
    fallback_count: int
    timeout_count: int
    stale_count: int
    commitment_failures: int
    records: list[dict] = field(default_factory=list)


def run_robust_episode(
    instance: Instance,
    releases: list[tuple[str, float]],
    controller: SafeTimeController,
    *,
    fleet_size: int,
    t_max: float,
    replan_interval: float,
    advance_plant: bool = True,
    max_events: int = 5_000,
) -> RobustEpisode:
    simulator = FleetSimulator(instance, fleet_size)
    for customer_id, release_time in releases:
        simulator.schedule_release(customer_id, release_time)
    decisions: list[Decision] = []
    records: list[dict] = []
    stale_count = 0
    replan_id: int | None = None
    same_time = 0
    last_time = -1.0

    def decide(trigger: str) -> None:
        nonlocal replan_id, stale_count, same_time, last_time
        if abs(simulator.time - last_time) <= EPS:
            same_time += 1
        else:
            same_time = 0
            last_time = simulator.time
        if same_time > 32:
            raise RuntimeError("decision loop did not advance time")
        before = action_id(simulator.observation())
        proposal = controller.propose(simulator.observation(), trigger)
        elapsed = proposal.optimize_seconds
        nxt = simulator.next_event_time()
        crosses = advance_plant and nxt is not None and simulator.time + elapsed > nxt + EPS
        if crosses and proposal.audit and proposal.audit.get("replaced_backup"):
            controller.discard()
            proposal = controller.fallback_decision(simulator.observation(), "stale_physical_event")
            stale_count += 1
            if proposal.audit is not None:
                proposal.audit["stale"] = True
        elif advance_plant and not crosses:
            simulator.time += elapsed
            if proposal.audit and proposal.audit.get("replaced_backup"):
                if action_id(simulator.observation()) != before or not controller.holds(simulator.observation()):
                    controller.discard()
                    proposal = controller.fallback_decision(simulator.observation(), "revalidation_failed")
                    stale_count += 1
                else:
                    controller.commit(simulator.observation())
            elif proposal.audit and proposal.audit.get("replaced_backup") is False:
                controller.discard()
        else:
            if proposal.audit and proposal.audit.get("replaced_backup"):
                if controller.holds(simulator.observation()):
                    controller.commit(simulator.observation())
                else:
                    controller.discard()
                    proposal = controller.fallback_decision(simulator.observation(), "revalidation_failed")
        decisions.append(proposal)
        if proposal.audit is not None:
            records.append(dict(proposal.audit))
        simulator.apply_decision(proposal)
        if replan_id is not None:
            simulator.cancel(replan_id)
        replan_id = simulator.schedule_replan(simulator.time + replan_interval)

    if simulator.next_event_time() is None or simulator.next_event_time() > EPS:
        decide("initial")
    events = 0
    while events < max_events:
        nxt = simulator.next_event_time()
        if nxt is None or nxt > t_max + EPS:
            break
        event = simulator.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decide(event.kind)
        if _done(simulator):
            break
    else:
        raise RuntimeError("event limit reached")
    simulator.mark_finished()
    failures = sum(1 for status in simulator.requests.values() if status.value == "accepted_unfulfilled")
    return RobustEpisode(
        decisions=decisions,
        final_requests={cid: status.value for cid, status in simulator.requests.items()},
        optimize_count=sum(1 for record in records if record.get("optimize")),
        fallback_count=sum(1 for record in records if record.get("fallback")),
        timeout_count=sum(1 for record in records if record.get("timeout")),
        stale_count=stale_count,
        commitment_failures=failures,
        records=records,
    )


def _done(simulator: FleetSimulator) -> bool:
    open_status = {"announced", "accepted", "deferred", "in_service"}
    if any(status.value in open_status for status in simulator.requests.values()):
        return False
    return all(
        vehicle.status.value == "idle" and vehicle.node == simulator.instance.depot_id
        for vehicle in simulator.vehicles.values()
    )
