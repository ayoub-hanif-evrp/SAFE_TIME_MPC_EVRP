"""FleetSimulator-backed causal evaluation of first actions.

Scenarios reveal customers only at their release times. After the shared first
decision, recourse is forecast-blind reactive insertion on the public observation.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.state import Decision, RequestStatus, Visit
from safe_time_evrp.mpc_central.forks import ForkSpec
from safe_time_evrp.validation.replay import validate_log

SERVICE_REWARD = 100.0
DISTANCE_PENALTY = 1.0
UNFULFILLED_PENALTY = 250.0

_TRIGGERS = frozenset({"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan"})


@dataclass(frozen=True)
class PlantEpisodeScore:
    action: str
    scenario_index: int
    completed: tuple[str, ...]
    accepted_unfulfilled: tuple[str, ...]
    value: float
    replay_ok: bool
    end_time: float
    notes: tuple[str, ...]
    log_kinds: tuple[str, ...] = ()


def action_to_decision(spec: ForkSpec, action: str, *, vehicle_id: str) -> Decision:
    accepted = list(spec.observation.accepted)
    newly: list[str] = []
    rejected: list[str] = []
    routes: dict[str, list[Visit]] = {vehicle_id: []}

    prior = list(spec.prior_accepted)
    if action == "serve_near":
        newly = ["Near"]
        accepted = list(dict.fromkeys([*accepted, "Near"]))
        routes[vehicle_id] = [Visit("Near", "service")]
    elif action == "charge_first":
        routes[vehicle_id] = [Visit("S", "charge")]
    elif action == "accept_now":
        newly = ["Now"]
        accepted = list(dict.fromkeys([*accepted, "Now"]))
        # If prior commitments exist, a legal accept must still cover them in-plan.
        prefix = [Visit(cid, "service") for cid in prior]
        routes[vehicle_id] = [*prefix, Visit("Now", "service")]
    elif action == "reject_now":
        rejected = ["Now"]
        if prior:
            routes[vehicle_id] = [Visit(cid, "service") for cid in prior]
    elif action == "serve_must":
        routes[vehicle_id] = [Visit("Must", "service")]
        # Do not greedily accept Now in the first decision; keep it open or reject.
        if "Now" in spec.observation.released_open:
            rejected = ["Now"]
    elif action == "charge_then_must":
        routes[vehicle_id] = [Visit("S", "charge"), Visit("Must", "service")]
    else:
        raise ValueError(f"unknown action {action}")

    return Decision(
        time=spec.observation.time,
        routes=routes,
        accepted=accepted,
        newly_accepted=newly,
        rejected=rejected,
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=sorted({v.node_id for vs in routes.values() for v in vs if v.purpose == "service"}),
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="initial",
        locked_destinations={},
        notes=[f"first_action={action}"],
        audit={"mpc_central_first_action": action},
    )


def _releases(spec: ForkSpec, scenario: tuple[tuple[str, float], ...]) -> list[tuple[str, float]]:
    out = list(spec.base_releases)
    seen = {cid for cid, _ in out}
    for cid, t in scenario:
        if cid not in seen:
            out.append((cid, t))
            seen.add(cid)
    return out


def _prepare_sim(spec: ForkSpec, scenario: tuple[tuple[str, float], ...]) -> FleetSimulator:
    energy = NominalLinearEnergy()
    sim = FleetSimulator(spec.instance, fleet_size=1, energy=energy)
    # Do not patch SOC after init — replay trusts vehicle_init. Forks must set
    # battery_capacity to the intended start SOC.
    for cid, t in _releases(spec, scenario):
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= EPS:
        sim.pop_event()
    for cid in spec.prior_accepted:
        status = sim.requests.get(cid)
        if status is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.ANNOUNCED
            status = RequestStatus.ANNOUNCED
        if status in {RequestStatus.ANNOUNCED, RequestStatus.DEFERRED}:
            sim.requests[cid] = RequestStatus.ACCEPTED
    return sim


def evaluate_action_scenario(
    spec: ForkSpec,
    action: str,
    scenario: tuple[tuple[str, float], ...],
    *,
    scenario_index: int = 0,
    horizon: float = 200.0,
    max_replan_interval: float = 5.0,
) -> PlantEpisodeScore:
    del max_replan_interval  # reactive MPC schedules its own replans via episode triggers
    sim = _prepare_sim(spec, scenario)
    vid = next(iter(sim.vehicles))
    first = action_to_decision(spec, action, vehicle_id=vid)
    notes: list[str] = []

    if spec.prior_accepted:
        val = validate_continuation(spec.instance, sim.observation(), first.routes)
        pending = set(spec.prior_accepted) - set(sim.observation().in_service)
        covered = set(val.served) | set(sim.observation().in_service)
        # Also count immediate service visits in the first decision.
        covered |= {v.node_id for vs in first.routes.values() for v in vs if v.purpose == "service"}
        if pending - covered and action == "accept_now":
            # Accepting Now without covering Must in the same plan is unsafe if Must not in route.
            if pending - covered:
                notes.append("unsafe_prior_commitment_uncovered")
                return PlantEpisodeScore(
                    action=action,
                    scenario_index=scenario_index,
                    completed=(),
                    accepted_unfulfilled=tuple(sorted(pending)),
                    value=-1e9,
                    replay_ok=True,
                    end_time=sim.time,
                    notes=tuple(notes),
                )

    try:
        sim.apply_decision(first)
    except SimulatorError as exc:
        notes.append(f"dispatch_rejected:{exc}")
        return PlantEpisodeScore(
            action=action,
            scenario_index=scenario_index,
            completed=(),
            accepted_unfulfilled=tuple(spec.prior_accepted),
            value=-1e9,
            replay_ok=True,
            end_time=sim.time,
            notes=tuple(notes),
        )
    reactive = EventTriggeredMPC(spec.instance, horizon=horizon)
    events = 0
    replan_every = 8.0
    next_force = sim.time + replan_every
    while events < 20_000:
        nxt = sim.next_event_time()
        # Forced replan ticks so idle fleets reconsider after releases.
        if nxt is None or (nxt > next_force + EPS and sim.time + EPS < spec.t_max):
            if sim.time + EPS >= spec.t_max:
                break
            # Advance time via a no-op wait only if there is a future event beyond force.
            if nxt is not None and nxt <= spec.t_max + EPS:
                # Insert a decide at next_force by waiting until min(nxt, next_force) — plant has no wait API.
                # Fall through to pop if nxt <= next_force; else decide now while idle.
                idle = all(v.status.value == "idle" for v in sim.vehicles.values())
                if idle and sim.time + EPS >= next_force:
                    decision = reactive.decide(sim.observation(), "replan")
                    if decision.routes and vid not in decision.routes:
                        decision.routes = {vid: next(iter(decision.routes.values()))}
                    sim.apply_decision(decision)
                    next_force = sim.time + replan_every
                    continue
        if nxt is None or nxt > spec.t_max + EPS:
            break
        event = sim.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decision = reactive.decide(sim.observation(), event.kind)
            if decision.routes and vid not in decision.routes:
                decision.routes = {vid: next(iter(decision.routes.values()))}
            sim.apply_decision(decision)
            next_force = sim.time + replan_every
        open_status = {"announced", "accepted", "deferred", "in_service"}
        if not any(s.value in open_status for s in sim.requests.values()):
            if all(v.status.value == "idle" and v.node == spec.instance.depot_id for v in sim.vehicles.values()):
                break

    sim.mark_finished()
    report = validate_log(spec.instance, sim.log)
    completed = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "completed"))
    au = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "accepted_unfulfilled"))
    dist = sum(float(rec.data.get("distance") or 0.0) for rec in sim.log if rec.kind == "depart")
    value = SERVICE_REWARD * len(completed) - UNFULFILLED_PENALTY * len(au) - DISTANCE_PENALTY * dist
    notes.append(f"events={events}")
    return PlantEpisodeScore(
        action=action,
        scenario_index=scenario_index,
        completed=completed,
        accepted_unfulfilled=au,
        value=value,
        replay_ok=report.ok,
        end_time=sim.time,
        notes=tuple(notes),
        log_kinds=tuple(rec.kind for rec in sim.log),
    )


def expected_action_value(spec: ForkSpec, action: str, **kwargs) -> tuple[float, tuple[PlantEpisodeScore, ...]]:
    scores = tuple(
        evaluate_action_scenario(spec, action, sc, scenario_index=i, **kwargs) for i, sc in enumerate(spec.scenarios)
    )
    exp = sum(p * s.value for p, s in zip(spec.scenario_probs, scores, strict=True))
    return exp, scores


def early_service_before_release(spec: ForkSpec, action: str, scenario: tuple[tuple[str, float], ...]) -> list[str]:
    """Return customer IDs that were departed-to or served before their release time."""
    sim = _prepare_sim(spec, scenario)
    vid = next(iter(sim.vehicles))
    sim.apply_decision(action_to_decision(spec, action, vehicle_id=vid))
    release_at = {cid: t for cid, t in _releases(spec, scenario)}
    bad: list[str] = []
    # Also process events until first release of scenario customers while checking log growth.
    reactive = EventTriggeredMPC(spec.instance, horizon=200.0)
    for _ in range(5000):
        nxt = sim.next_event_time()
        if nxt is None or nxt > spec.t_max + EPS:
            break
        event = sim.pop_event()
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decision = reactive.decide(sim.observation(), event.kind)
            if decision.routes and vid not in decision.routes:
                decision.routes = {vid: next(iter(decision.routes.values()))}
            # Guard: refuse routes that target still-hidden customers.
            hidden = {cid for cid, st in sim.requests.items() if st is RequestStatus.HIDDEN}
            cleaned = []
            for visit in decision.routes.get(vid, []):
                if visit.node_id in hidden:
                    bad.append(visit.node_id)
                    continue
                cleaned.append(visit)
            decision.routes[vid] = cleaned
            sim.apply_decision(decision)
        for rec in sim.log[-5:]:
            if rec.kind == "depart":
                dest = rec.data.get("destination")
                if dest in release_at and rec.time + EPS < release_at[dest]:
                    bad.append(str(dest))
            if rec.kind == "service_start":
                # customer id is the vehicle locked dest / record node conventions
                node = rec.data.get("node") or rec.data.get("customer")
                if node in release_at and rec.time + EPS < release_at[node]:
                    bad.append(str(node))
    return sorted(set(bad))


def clairvoyant_route_would_leak(spec: ForkSpec) -> bool:
    """A deliberately illegal planner that inserts unreleased scenario customers into the first route."""
    for sc in spec.scenarios:
        if not sc:
            continue
        cid, release_t = sc[0]
        if release_t <= EPS:
            continue
        sim = _prepare_sim(spec, sc)
        vid = next(iter(sim.vehicles))
        # Illegal: dispatch toward unreleased customer immediately.
        illegal = Decision(
            time=0.0,
            routes={vid: [Visit(cid, "service")]},
            accepted=list(spec.observation.accepted),
            newly_accepted=[],
            rejected=[],
            deferred=[],
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=[cid],
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=0.0,
            trigger="illegal_peek",
            locked_destinations={},
            notes=["clairvoyant_leak"],
        )
        # Plant should not have announced cid yet.
        assert sim.requests[cid] is RequestStatus.HIDDEN
        sim.apply_decision(illegal)
        for rec in sim.log:
            if rec.kind == "depart" and rec.data.get("destination") == cid and rec.time + EPS < release_t:
                return True
            if rec.kind == "service_start" and (rec.data.get("node") == cid or rec.data.get("customer") == cid):
                if rec.time + EPS < release_t:
                    return True
        # If plant refuses to start (no depart), still a logical leak at decision level.
        if any(v.node_id == cid for v in illegal.routes[vid]):
            return True
    return False
