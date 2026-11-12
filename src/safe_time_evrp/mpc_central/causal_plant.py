"""FleetSimulator-backed causal evaluation of first actions.

Scenarios reveal customers only at their release times. After the shared first
decision, default recourse is B1-style commitment-validated insertion
(``recourse='b1_validated'``). Raw insertion remains available as a labeled baseline
(``recourse='insertion'``). Executed distance is reconstructed from the arc table
via ``executed_distance_from_log`` (depart records do not store distance). Periodic
``replan_interval`` events match ``run_episode``.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.state import Decision, Observation, RequestStatus, Visit
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

    if action == "serve_near":
        newly = ["Near"]
        accepted = list(dict.fromkeys([*accepted, "Near"]))
        routes[vehicle_id] = [Visit("Near", "service")]
    elif action == "charge_first":
        routes[vehicle_id] = [Visit("S", "charge")]
    elif action == "accept_now":
        newly = ["Now"]
        accepted = list(dict.fromkeys([*accepted, "Now"]))
        routes[vehicle_id] = [Visit("Now", "service")]
    elif action == "reject_now":
        rejected = ["Now"]
    elif action == "accept_now_after_must":
        # Single-tour accept (capacity must allow Must+Now together).
        newly = ["Now"]
        accepted = list(dict.fromkeys([*accepted, "Now"]))
        routes[vehicle_id] = [Visit("Must", "service"), Visit("Now", "service")]
    elif action == "accept_now_reload":
        newly = ["Now"]
        accepted = list(dict.fromkeys([*accepted, "Now"]))
        depot = spec.instance.depot_id
        routes[vehicle_id] = [Visit("Must", "service"), Visit(depot, "reload"), Visit("Now", "service")]
    elif action == "reject_now_serve_must":
        rejected = ["Now"]
        routes[vehicle_id] = [Visit("Must", "service")]
    elif action == "serve_must":
        routes[vehicle_id] = [Visit("Must", "service")]
        if "Now" in spec.observation.released_open:
            rejected = ["Now"]
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
    if spec.prior_accepted:
        vid = next(iter(sim.vehicles))
        # Legal logged acceptance (no direct request-map mutation).
        seed = Decision(
            time=sim.time,
            routes={vid: []},
            accepted=list(spec.prior_accepted),
            newly_accepted=list(spec.prior_accepted),
            rejected=[],
            deferred=[],
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=[],
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=0.0,
            trigger="seed_prior_commitments",
            locked_destinations={},
            notes=["seed_prior_commitments"],
        )
        sim.apply_decision(seed)
    return sim


class B1ValidatedRecourse:
    """Insertion proposals with independent nominal continuation validation (B1-style).

    Heavier than raw EventTriggeredMPC; lighter than full ALNS–B1. Used as the
    default scenario-recourse policy for safety-relevant experiments.
    """

    def __init__(self, instance, horizon: float) -> None:
        self._inner = EventTriggeredMPC(instance, horizon)
        self._instance = instance
        self._verified: dict[str, list[Visit]] | None = None

    def decide(self, observation: Observation, trigger: str) -> Decision:
        raw = self._inner.decide(observation, trigger)
        report = validate_continuation(
            self._instance,
            observation,
            raw.routes,
            require_new=frozenset(raw.newly_accepted),
        )
        notes = list(raw.notes) + ["b1_validated_recourse"]
        if report.ok:
            newly = [c for c in raw.newly_accepted if c in report.served]
            self._verified = {vid: list(vs) for vid, vs in raw.routes.items()}
            accepted = list(observation.accepted)
            for c in newly:
                if c not in accepted:
                    accepted.append(c)
            return Decision(
                time=raw.time,
                routes=raw.routes,
                accepted=accepted,
                newly_accepted=newly,
                rejected=[c for c in raw.rejected if c not in newly],
                deferred=list(raw.deferred),
                fallback_used=False,
                no_feasible_continuation=False,
                horizon_extended=raw.horizon_extended,
                planned_service=list(raw.planned_service),
                total_distance=raw.total_distance,
                total_charge_time=raw.total_charge_time,
                optimize_seconds=raw.optimize_seconds,
                trigger=trigger,
                locked_destinations=dict(raw.locked_destinations),
                notes=notes + ["validated_with_new_accepts" if newly else "validated_commitments_only"],
                audit={"validation_status": "CERTIFIED_FEASIBLE", **(raw.audit or {})},
            )
        # Drop new accepts; try commitments only.
        report2 = validate_continuation(self._instance, observation, raw.routes, require_new=frozenset())
        if report2.ok:
            self._verified = {vid: list(vs) for vid, vs in raw.routes.items()}
            return Decision(
                time=raw.time,
                routes=raw.routes,
                accepted=list(observation.accepted),
                newly_accepted=[],
                rejected=list(raw.rejected) + list(raw.newly_accepted),
                deferred=list(raw.deferred),
                fallback_used=True,
                no_feasible_continuation=False,
                horizon_extended=raw.horizon_extended,
                planned_service=list(raw.planned_service),
                total_distance=raw.total_distance,
                total_charge_time=raw.total_charge_time,
                optimize_seconds=raw.optimize_seconds,
                trigger=trigger,
                locked_destinations=dict(raw.locked_destinations),
                notes=notes + ["rejected_unvalidated_new_accepts"],
                audit={"validation_status": "CERTIFIED_FEASIBLE", **(raw.audit or {})},
            )
        if self._verified is not None:
            prev = validate_continuation(self._instance, observation, self._verified, require_new=frozenset())
            if prev.ok:
                return Decision(
                    time=raw.time,
                    routes={vid: list(vs) for vid, vs in self._verified.items()},
                    accepted=list(observation.accepted),
                    newly_accepted=[],
                    rejected=list(raw.newly_accepted),
                    deferred=[],
                    fallback_used=True,
                    no_feasible_continuation=False,
                    horizon_extended=False,
                    planned_service=[],
                    total_distance=0.0,
                    total_charge_time=0.0,
                    optimize_seconds=raw.optimize_seconds,
                    trigger=trigger,
                    locked_destinations={},
                    notes=notes + ["reused_previous_witness"],
                    audit={"validation_status": "CERTIFIED_FEASIBLE"},
                )
        return Decision(
            time=raw.time,
            routes={v.id: [] for v in observation.vehicles},
            accepted=list(observation.accepted),
            newly_accepted=[],
            rejected=list(raw.newly_accepted),
            deferred=[],
            fallback_used=True,
            no_feasible_continuation=True,
            horizon_extended=False,
            planned_service=[],
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=raw.optimize_seconds,
            trigger=trigger,
            locked_destinations={},
            notes=notes + ["status=UNKNOWN"],
            audit={"validation_status": "UNKNOWN"},
        )


def evaluate_action_scenario(
    spec: ForkSpec,
    action: str,
    scenario: tuple[tuple[str, float], ...],
    *,
    scenario_index: int = 0,
    horizon: float = 200.0,
    max_replan_interval: float = 5.0,
    recourse: str = "b1_validated",
) -> PlantEpisodeScore:
    sim = _prepare_sim(spec, scenario)
    vid = next(iter(sim.vehicles))
    first = action_to_decision(spec, action, vehicle_id=vid)
    notes: list[str] = [f"recourse={recourse}"]

    # Refuse first decisions that name still-hidden customers.
    hidden = {cid for cid, st in sim.requests.items() if st is RequestStatus.HIDDEN}
    for visit in first.routes.get(vid, []):
        if visit.node_id in hidden:
            notes.append(f"illegal_unreleased_target:{visit.node_id}")
            report = validate_log(spec.instance, sim.log)
            return PlantEpisodeScore(
                action=action,
                scenario_index=scenario_index,
                completed=(),
                accepted_unfulfilled=tuple(spec.prior_accepted),
                value=-1e9,
                replay_ok=report.ok,
                end_time=sim.time,
                notes=tuple(notes),
                log_kinds=tuple(rec.kind for rec in sim.log),
            )

    require_new = frozenset(first.newly_accepted) if first.newly_accepted else None
    val = validate_continuation(
        spec.instance,
        sim.observation(),
        first.routes,
        require_new=require_new,
    )
    if (spec.prior_accepted or first.newly_accepted) and not val.ok:
        notes.append("validate_continuation_failed")
        notes.extend(val.reasons[:3])
        report = validate_log(spec.instance, sim.log)
        return PlantEpisodeScore(
            action=action,
            scenario_index=scenario_index,
            completed=(),
            accepted_unfulfilled=tuple(spec.prior_accepted),
            value=-1e9,
            replay_ok=report.ok,
            end_time=sim.time,
            notes=tuple(notes),
            log_kinds=tuple(rec.kind for rec in sim.log),
        )

    try:
        sim.apply_decision(first)
    except SimulatorError as exc:
        notes.append(f"dispatch_rejected:{exc}")
        report = validate_log(spec.instance, sim.log)
        return PlantEpisodeScore(
            action=action,
            scenario_index=scenario_index,
            completed=(),
            accepted_unfulfilled=tuple(spec.prior_accepted),
            value=-1e9,
            replay_ok=report.ok,
            end_time=sim.time,
            notes=tuple(notes),
            log_kinds=tuple(rec.kind for rec in sim.log),
        )

    if recourse == "insertion":
        controller: EventTriggeredMPC | B1ValidatedRecourse = EventTriggeredMPC(spec.instance, horizon=horizon)
    else:
        controller = B1ValidatedRecourse(spec.instance, horizon=horizon)

    # Match run_episode: schedule periodic replans on the plant event heap.
    replan_id = sim.schedule_replan(sim.time + max_replan_interval)
    events = 0
    while events < 20_000:
        nxt = sim.next_event_time()
        if nxt is None or nxt > spec.t_max + EPS:
            break
        event = sim.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS or event.kind == "replan_interval":
            decision = controller.decide(sim.observation(), event.kind)
            if decision.routes and vid not in decision.routes and decision.routes:
                decision.routes = {vid: next(iter(decision.routes.values()))}
            # Strip any still-hidden targets from routes.
            hidden_now = {cid for cid, st in sim.requests.items() if st is RequestStatus.HIDDEN}
            cleaned = {
                v_id: [vis for vis in visits if vis.node_id not in hidden_now]
                for v_id, visits in decision.routes.items()
            }
            decision.routes = cleaned
            sim.apply_decision(decision)
            if replan_id is not None:
                sim.cancel(replan_id)
            replan_id = sim.schedule_replan(sim.time + max_replan_interval)
        open_status = {"announced", "accepted", "deferred", "in_service"}
        if not any(s.value in open_status for s in sim.requests.values()):
            if all(v.status.value == "idle" and v.node == spec.instance.depot_id for v in sim.vehicles.values()):
                break

    sim.mark_finished()
    report = validate_log(spec.instance, sim.log)
    completed = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "completed"))
    au = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "accepted_unfulfilled"))
    dist = executed_distance_from_log(spec.instance, sim.log)
    value = SERVICE_REWARD * len(completed) - UNFULFILLED_PENALTY * len(au) - DISTANCE_PENALTY * dist
    notes.append(f"events={events}")
    notes.append(f"executed_distance={dist:.6f}")
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
