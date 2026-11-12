"""Causal closed-loop scenario rollouts from a public observation (Phase 3D).

Forks a FleetSimulator seeded from the current observation (busy vehicles start
from their post-action anchors), injects information-safe forecast releases, applies
a candidate first decision, then continues with B1-validated recourse. Same scoring
contract as ``causal_plant``.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, RequestStatus, VehicleStatus
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, augment_instance_for_planning
from safe_time_evrp.mpc_central.causal_plant import (
    DISTANCE_PENALTY,
    SERVICE_REWARD,
    UNFULFILLED_PENALTY,
    B1ValidatedRecourse,
)
from safe_time_evrp.validation.replay import validate_log

_TRIGGERS = frozenset(
    {"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan", "replan_interval"}
)


@dataclass(frozen=True)
class ScenarioRolloutScore:
    value: float
    completed: tuple[str, ...]
    accepted_unfulfilled: tuple[str, ...]
    executed_distance: float
    replay_ok: bool
    events: int
    notes: tuple[str, ...]


def seed_simulator_from_observation(
    instance: Instance,
    observation: Observation,
    *,
    energy: NominalLinearEnergy | None = None,
) -> FleetSimulator:
    """Build a plant fork whose public state matches ``observation``.

    Busy vehicles are placed at their post-action ``anchor`` and marked idle so the
    candidate first decision is the next executable plan (MPC decision epoch).
    """
    fleet_size = len(observation.vehicles)
    sim = FleetSimulator(instance, fleet_size=fleet_size, energy=energy)
    sim.time = float(observation.time)

    # Remap default v1..vn if observation uses those ids.
    id_map = {f"v{i + 1}": observation.vehicles[i].id for i in range(fleet_size)}
    if any(v.id != f"v{i + 1}" for i, v in enumerate(observation.vehicles)):
        # Rebuild vehicles dict under observation ids.
        new_vehicles = {}
        for i, view in enumerate(observation.vehicles):
            old = sim.vehicles[f"v{i + 1}"]
            old.id = view.id
            new_vehicles[view.id] = old
        sim.vehicles = new_vehicles
    else:
        id_map = {v.id: v.id for v in observation.vehicles}

    for view in observation.vehicles:
        vehicle = sim.vehicles[view.id]
        vehicle.node = view.anchor.node
        vehicle.soc = view.anchor.soc
        vehicle.load = view.anchor.load
        vehicle.onboard = set(view.anchor.onboard)
        vehicle.status = VehicleStatus.IDLE
        vehicle.suffix = []
        vehicle.action = None
        vehicle.anchor_after = None
        vehicle.locked_destination = None
        vehicle.wait_customer = None

    # Request statuses visible in the observation; unknown customers stay HIDDEN.
    known_customers = set(instance.customer_ids())
    for cid in known_customers:
        sim.requests[cid] = RequestStatus.HIDDEN
    for cid in observation.completed:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.COMPLETED
    for cid in observation.rejected:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.REJECTED
    for cid in observation.in_service:
        if cid in sim.requests:
            # Treat in-service as accepted at the decision epoch after anchoring.
            sim.requests[cid] = RequestStatus.ACCEPTED
    for cid in observation.accepted:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.ACCEPTED
    for cid in observation.deferred:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.DEFERRED
    for cid in observation.released_open:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.ANNOUNCED

    _ = id_map  # documented for callers that remap fleets
    return sim


def rollout_candidate(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    forecasts: list[ForecastCustomer],
    *,
    horizon: float,
    t_max: float | None = None,
    max_replan_interval: float = 5.0,
    max_events: int = 2_000,
    energy: NominalLinearEnergy | None = None,
) -> ScenarioRolloutScore:
    """Causal closed-loop value of ``candidate`` under one forecast scenario."""
    model = energy or NominalLinearEnergy()
    notes: list[str] = ["causal_scenario_rollout", "recourse=b1_validated"]
    planning = augment_instance_for_planning(full_instance, forecasts)
    # Public geometry for seeding must include currently released customers.
    sim = seed_simulator_from_observation(planning, observation, energy=model)
    horizon_end = observation.time + (t_max if t_max is not None else horizon)

    for fc in forecasts:
        if fc.customer_id not in sim.requests:
            continue
        release_t = max(float(fc.ready_time), float(observation.time))
        try:
            sim.schedule_release(fc.customer_id, release_t)
        except Exception as exc:  # noqa: BLE001 — keep rollout scoring resilient
            notes.append(f"release_skip:{fc.customer_id}:{exc}")

    # Apply candidate; strip targets unknown to the scenario plant.
    routes = {vid: [vis for vis in visits if vis.node_id in planning.nodes] for vid, visits in candidate.routes.items()}
    first = Decision(
        time=observation.time,
        routes=routes,
        accepted=list(candidate.accepted),
        newly_accepted=[c for c in candidate.newly_accepted if c in planning.nodes],
        rejected=[c for c in candidate.rejected if c in planning.nodes],
        deferred=list(candidate.deferred),
        fallback_used=candidate.fallback_used,
        no_feasible_continuation=candidate.no_feasible_continuation,
        horizon_extended=False,
        planned_service=list(candidate.planned_service),
        total_distance=candidate.total_distance,
        total_charge_time=candidate.total_charge_time,
        optimize_seconds=0.0,
        trigger="scenario_first",
        locked_destinations={},
        notes=["scenario_first_action"],
    )
    try:
        sim.apply_decision(first)
    except SimulatorError as exc:
        notes.append(f"dispatch_rejected:{exc}")
        return ScenarioRolloutScore(
            value=-1e9,
            completed=(),
            accepted_unfulfilled=tuple(observation.accepted),
            executed_distance=0.0,
            replay_ok=False,
            events=0,
            notes=tuple(notes),
        )

    controller = B1ValidatedRecourse(planning, horizon=horizon)
    replan_id = sim.schedule_replan(sim.time + max_replan_interval)
    events = 0
    while events < max_events:
        nxt = sim.next_event_time()
        if nxt is None or nxt > horizon_end + EPS:
            break
        event = sim.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decision = controller.decide(sim.observation(), event.kind)
            hidden = {cid for cid, st in sim.requests.items() if st is RequestStatus.HIDDEN}
            decision.routes = {
                vid: [vis for vis in visits if vis.node_id not in hidden] for vid, visits in decision.routes.items()
            }
            try:
                sim.apply_decision(decision)
            except SimulatorError as exc:
                notes.append(f"recourse_rejected:{exc}")
                break
            if replan_id is not None:
                sim.cancel(replan_id)
            replan_id = sim.schedule_replan(sim.time + max_replan_interval)

    sim.mark_finished()
    report = validate_log(planning, sim.log)
    completed = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "completed"))
    au = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "accepted_unfulfilled"))
    dist = executed_distance_from_log(planning, sim.log)
    value = SERVICE_REWARD * len(completed) - UNFULFILLED_PENALTY * len(au) - DISTANCE_PENALTY * dist
    notes.append(f"events={events}")
    notes.append(f"executed_distance={dist:.6f}")
    return ScenarioRolloutScore(
        value=value,
        completed=completed,
        accepted_unfulfilled=au,
        executed_distance=dist,
        replay_ok=report.ok,
        events=events,
        notes=tuple(notes),
    )


def expected_rollout_value(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    scenario_forecasts: list[list[ForecastCustomer]],
    *,
    horizon: float,
    max_scenarios: int | None = None,
    **kwargs,
) -> tuple[float, tuple[ScenarioRolloutScore, ...]]:
    """Mean causal value over forecast scenarios (equal weight; CRN-friendly index order)."""
    scenarios = scenario_forecasts if max_scenarios is None else scenario_forecasts[:max_scenarios]
    if not scenarios:
        # No forecast: score the candidate by nominal commitment coverage only.
        from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
        from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot

        public = make_public_snapshot(full_instance, observation, horizon).instance
        rep = validate_continuation(
            public,
            observation,
            candidate.routes,
            require_new=frozenset(candidate.newly_accepted),
        )
        value = (100.0 * len(rep.served) - rep.distance) if rep.ok else -1e9
        score = ScenarioRolloutScore(
            value=value,
            completed=tuple(rep.served),
            accepted_unfulfilled=(),
            executed_distance=rep.distance,
            replay_ok=rep.ok,
            events=0,
            notes=("no_forecast_nominal_only",),
        )
        return value, (score,)
    scores = tuple(
        rollout_candidate(full_instance, observation, candidate, fcs, horizon=horizon, **kwargs) for fcs in scenarios
    )
    return sum(s.value for s in scores) / len(scores), scores
