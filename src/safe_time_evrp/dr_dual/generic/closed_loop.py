"""Receding-horizon driver: continues until future releases + commitments + depot are done."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.generic.actions import (
    episode_complete,
    legal_fleet_actions,
    pending_future_releases,
    release_due_announcements,
)
from safe_time_evrp.dr_dual.generic.model import initial_generic_state
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.solver import solve_dr_dual
from safe_time_evrp.dr_dual.state import PlantLog
from safe_time_evrp.dr_dual.transition import apply_action


def _parse_action_key(key: str) -> Action:
    parts = key.split("|")
    kind = ActionKind(parts[0])
    vid = parts[1]
    seg = None if parts[2] == "None" else parts[2]
    cust = None if parts[3] == "None" else parts[3]
    chg = None if parts[4] == "None" else parts[4]
    wait = float(parts[5])
    return Action(kind, vid, segment_id=seg, customer_id=cust, charger_id=chg, wait_duration=wait)


@dataclass
class ClosedLoopResult:
    total_reward: float
    steps: int
    completed: frozenset[str]
    model_inconsistent: bool
    log: PlantLog
    notes: tuple[str, ...]


def run_closed_loop(
    net: RoadNetwork,
    *,
    theta_star: float,
    max_steps: int = 40,
    bound_mode: str = "generic",
    use_pruning: bool = False,
    noise: float = 0.0,
) -> ClosedLoopResult:
    state = initial_generic_state(net)
    log = PlantLog()
    reward = 0.0
    notes: list[str] = []
    steps = 0
    for _ in range(max_steps):
        state = release_due_announcements(net, state)
        if state.model_inconsistent:
            notes.append("abort_model_inconsistent")
            break
        if episode_complete(net, state):
            notes.append("episode_complete")
            break
        # Still active if future releases exist even when accepted set is currently empty/done
        if state.accepted.issubset(state.completed) and pending_future_releases(net, state):
            notes.append("awaiting_future_release")
        stats = solve_dr_dual(net, state=state, use_pruning=use_pruning, bound_mode=bound_mode, noise=noise)
        if stats.selected_action is None:
            acts = legal_fleet_actions(net, state)
            if not acts:
                # Wait for next release if any
                if pending_future_releases(net, state):
                    from safe_time_evrp.dr_dual.generic.actions import global_clock

                    announce_at = net.metadata.get("announce_at", {})
                    clock = global_clock(state)
                    nxt = min(
                        float(t)
                        for cid, t in announce_at.items()
                        if float(t) > clock + 1e-12 and cid not in state.announced
                    )
                    vid = state.vehicles[0].vehicle_id
                    action = Action(ActionKind.WAIT, vid, wait_duration=nxt - state.vehicle(vid).time)
                else:
                    notes.append("no_legal_action")
                    break
            else:
                action = acts[0]
        else:
            action = _parse_action_key(stats.selected_action)
        tr = apply_action(net, state, action, theta_star=theta_star, noise=noise, log=log)
        steps += 1
        if tr.state is None:
            notes.append(f"transition_failed:{tr.note}")
            break
        reward += tr.reward_delta
        state = tr.state
        if tr.model_inconsistent:
            notes.append("model_inconsistent_after_travel")
            break
    return ClosedLoopResult(
        total_reward=reward,
        steps=steps,
        completed=state.completed,
        model_inconsistent=state.model_inconsistent,
        log=log,
        notes=tuple(notes),
    )
