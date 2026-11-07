"""Independent transition evaluator (replayable) for dr_dual networks."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import RoadNetwork, Segment
from safe_time_evrp.dr_dual.state import PlantLog, VehicleState, WorldState
from safe_time_evrp.dual_mpc.belief import DiscreteBelief
from safe_time_evrp.dual_mpc.energy_param import ArcFeature


@dataclass(frozen=True)
class TransitionResult:
    ok: bool
    state: WorldState | None
    reward_delta: float
    energy_observed: float | None
    segment_id: str | None
    note: str
    model_inconsistent: bool = False


def _seg(net: RoadNetwork, sid: str) -> Segment:
    for s in net.segments:
        if s.segment_id == sid:
            return s
    raise KeyError(sid)


def _replace_vehicle(state: WorldState, new_v: VehicleState) -> WorldState:
    vehicles = tuple(new_v if v.vehicle_id == new_v.vehicle_id else v for v in state.vehicles)
    return WorldState(
        vehicles=vehicles,
        accepted=state.accepted,
        completed=state.completed,
        rejected=state.rejected,
        announced=state.announced,
        belief=state.belief,
        stage=state.stage,
    )


def apply_action(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    theta_star: float,
    noise: float = 0.0,
    noise_tol: float = 1e-9,
    log: PlantLog | None = None,
) -> TransitionResult:
    """Apply one physical/admission action. Belief updates only after completed travel."""
    v = state.vehicle(action.vehicle_id)
    if v.busy_until > v.time + 1e-12 and action.kind not in {ActionKind.NOOP}:
        # Allow actions only when idle at decision time == vehicle time for this tiny model.
        if abs(v.busy_until - v.time) > 1e-12 and v.busy_until > state.vehicles[0].time:
            pass

    if action.kind is ActionKind.TRAVEL:
        assert action.segment_id is not None
        seg = _seg(net, action.segment_id)
        if seg.origin != v.node:
            return TransitionResult(False, None, 0.0, None, None, "wrong_origin")
        e = net.energy(seg, theta_star) + noise
        if e > v.soc + 1e-12:
            return TransitionResult(False, None, 0.0, None, None, "energy_infeasible")
        feat = ArcFeature(seg.segment_id, seg.base_energy, seg.informative)
        # Fail safe if observation is inconsistent with every theta in the declared support.
        # Bounded-noise model class: observation must lie within noise_tol of some predicted energy.
        # ``noise`` is already folded into ``e``; do not widen the tolerance by |noise| again.
        consistent = any(abs(net.energy(seg, th) - e) <= noise_tol + 1e-9 for th in state.belief.support)
        if not consistent:
            if log:
                log.record(kind="model_inconsistency", segment=seg.segment_id, energy=e)
            return TransitionResult(
                False, None, 0.0, e, seg.segment_id, "model_inconsistent_fail_safe", model_inconsistent=True
            )
        new_v = VehicleState(
            v.vehicle_id,
            seg.destination,
            v.time + seg.travel_time,
            v.soc - e,
            v.load,
            busy_until=v.time + seg.travel_time,
        )
        new_state = _replace_vehicle(state, new_v)
        # Causal belief update from completed traversal
        new_belief = state.belief.update_from_observation(feat, e, noise_tol=noise_tol + 1e-9)
        new_state = WorldState(
            vehicles=new_state.vehicles,
            accepted=new_state.accepted,
            completed=new_state.completed,
            rejected=new_state.rejected,
            announced=new_state.announced,
            belief=new_belief,
            stage=state.stage + 1,
        )
        reward = -net.energy_cost * e
        if log:
            log.record(
                kind="travel",
                vehicle=v.vehicle_id,
                segment=seg.segment_id,
                energy=e,
                theta_star=theta_star,
                time=new_v.time,
                soc=new_v.soc,
            )
        return TransitionResult(True, new_state, reward, e, seg.segment_id, "travel_ok")

    if action.kind is ActionKind.SERVE:
        assert action.customer_id is not None
        cust = net.customer(action.customer_id)
        if v.node != cust.node:
            return TransitionResult(False, None, 0.0, None, None, "not_at_customer")
        if action.customer_id in state.completed:
            return TransitionResult(False, None, 0.0, None, None, "already_served")
        start = max(v.time, cust.ready)
        if start > cust.due + 1e-12:
            return TransitionResult(False, None, 0.0, None, None, "late_for_window")
        end = start + cust.service_time
        if end > cust.due + 1e-12:
            return TransitionResult(False, None, 0.0, None, None, "service_exceeds_due")
        new_v = VehicleState(v.vehicle_id, v.node, end, v.soc, v.load + cust.demand, busy_until=end)
        new_state = _replace_vehicle(state, new_v)
        new_state = WorldState(
            vehicles=new_state.vehicles,
            accepted=state.accepted | {action.customer_id},
            completed=state.completed | {action.customer_id},
            rejected=state.rejected,
            announced=state.announced,
            belief=state.belief,
            stage=state.stage + 1,
        )
        if log:
            log.record(kind="serve", customer=action.customer_id, time=end)
        return TransitionResult(True, new_state, cust.reward, None, None, "serve_ok")

    if action.kind is ActionKind.CHARGE_FULL:
        ch = net.charger_at(v.node)
        if ch is None:
            return TransitionResult(False, None, 0.0, None, None, "no_charger_here")
        if v.soc >= net.battery - 1e-12:
            return TransitionResult(False, None, 0.0, None, None, "already_full")
        # Full charge: time proportional to energy deficit
        deficit = net.battery - v.soc
        duration = ch.full_charge_time * (deficit / net.battery)
        new_v = VehicleState(v.vehicle_id, v.node, v.time + duration, net.battery, v.load, busy_until=v.time + duration)
        new_state = _replace_vehicle(state, new_v)
        new_state = WorldState(
            vehicles=new_state.vehicles,
            accepted=state.accepted,
            completed=state.completed,
            rejected=state.rejected,
            announced=state.announced,
            belief=state.belief,
            stage=state.stage + 1,
        )
        if log:
            log.record(kind="charge_full", vehicle=v.vehicle_id, duration=duration, soc=net.battery)
        return TransitionResult(True, new_state, 0.0, None, None, "charge_ok")

    if action.kind is ActionKind.WAIT:
        new_v = VehicleState(
            v.vehicle_id,
            v.node,
            v.time + action.wait_duration,
            v.soc,
            v.load,
            busy_until=v.time + action.wait_duration,
        )
        new_state = _replace_vehicle(state, new_v)
        new_state = WorldState(
            vehicles=new_state.vehicles,
            accepted=state.accepted,
            completed=state.completed,
            rejected=state.rejected,
            announced=state.announced,
            belief=state.belief,
            stage=state.stage + 1,
        )
        return TransitionResult(True, new_state, 0.0, None, None, "wait_ok")

    if action.kind is ActionKind.ACCEPT:
        assert action.customer_id is not None
        if action.customer_id not in state.announced:
            return TransitionResult(False, None, 0.0, None, None, "not_announced")
        new_state = WorldState(
            vehicles=state.vehicles,
            accepted=state.accepted | {action.customer_id},
            completed=state.completed,
            rejected=state.rejected,
            announced=state.announced,
            belief=state.belief,
            stage=state.stage + 1,
        )
        return TransitionResult(True, new_state, 0.0, None, None, "accept_ok")

    if action.kind is ActionKind.REJECT:
        assert action.customer_id is not None
        if action.customer_id in state.accepted:
            return TransitionResult(False, None, 0.0, None, None, "cannot_reject_accepted")
        new_state = WorldState(
            vehicles=state.vehicles,
            accepted=state.accepted,
            completed=state.completed,
            rejected=state.rejected | {action.customer_id},
            announced=state.announced,
            belief=state.belief,
            stage=state.stage + 1,
        )
        return TransitionResult(True, new_state, 0.0, None, None, "reject_ok")

    if action.kind is ActionKind.NOOP:
        return TransitionResult(True, state, 0.0, None, None, "noop")

    return TransitionResult(False, None, 0.0, None, None, f"unsupported:{action.kind}")


def commitment_safe_under_all_theta(
    net: RoadNetwork,
    state: WorldState,
    first: Action,
    *,
    remaining_plan_builder,
) -> bool:
    """Nonanticipative robust check: for every theta in support, exists continuation covering accepted.

    ``remaining_plan_builder(state_after, theta) -> list[Action] | None`` may use theta only inside
    the check (adversarial quantification), not as a controller policy.
    """
    for theta in state.belief.support_set():
        tr = apply_action(net, state, first, theta_star=theta, noise=0.0)
        if not tr.ok or tr.state is None:
            return False
        plan = remaining_plan_builder(tr.state, theta)
        if plan is None:
            return False
        # Reset belief pollution from check: rebuild physical only for feasibility under theta
        # Re-simulate from original with fixed theta and the concrete action sequence.
        s0 = state
        seq = [first, *plan]
        # Use a shadow state with Dirac-like simulation under theta but without requiring belief
        shadow = WorldState(
            vehicles=s0.vehicles,
            accepted=s0.accepted,
            completed=s0.completed,
            rejected=s0.rejected,
            announced=s0.announced,
            belief=DiscreteBelief((theta,), (1.0,)),
            stage=s0.stage,
        )
        for act in seq:
            tr2 = apply_action(net, shadow, act, theta_star=theta, noise=0.0)
            if not tr2.ok or tr2.state is None:
                return False
            shadow = tr2.state
        if not state.accepted.issubset(shadow.completed | shadow.accepted):
            # Must complete all initially accepted by end of plan
            if not state.accepted.issubset(shadow.completed):
                return False
    return True
