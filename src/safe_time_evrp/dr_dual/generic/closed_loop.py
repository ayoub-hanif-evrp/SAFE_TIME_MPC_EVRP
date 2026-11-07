"""Receding-horizon driver: carries WorldState / belief across decision epochs."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.generic.actions import legal_actions, release_due_announcements
from safe_time_evrp.dr_dual.generic.model import initial_generic_state
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.solver import solve_dr_dual
from safe_time_evrp.dr_dual.state import PlantLog
from safe_time_evrp.dr_dual.transition import apply_action


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
    max_steps: int = 12,
    bound_mode: str = "generic",
    use_pruning: bool = True,
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
        if state.accepted.issubset(state.completed):
            if net.metadata.get("require_depot_return"):
                v = state.vehicles[0]
                depot = net.metadata.get("start_nodes", {}).get(v.vehicle_id, net.depot)
                if v.node == depot:
                    notes.append("terminal_ok")
                    break
            else:
                notes.append("commitments_done")
                break
        stats = solve_dr_dual(net, state=state, use_pruning=use_pruning, bound_mode=bound_mode, noise=noise)
        if stats.selected_action is None:
            # Fallback: any legal travel/serve
            acts = legal_actions(net, state, state.vehicles[0].vehicle_id)
            if not acts:
                notes.append("no_legal_action")
                break
            action = acts[0]
        else:
            # Reconstruct Action from key fields stored in travel|vid|seg|...
            parts = stats.selected_action.split("|")
            action = Action(ActionKind.TRAVEL, parts[1], segment_id=parts[2] if parts[2] != "None" else None)
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
        # Auto-serve if at accepted customer
        v = state.vehicle(action.vehicle_id)
        for c in net.customers:
            if c.customer_id in state.accepted and c.customer_id not in state.completed and c.node == v.node:
                sr = apply_action(
                    net,
                    state,
                    Action(ActionKind.SERVE, v.vehicle_id, customer_id=c.customer_id),
                    theta_star=theta_star,
                    log=log,
                )
                if sr.ok and sr.state is not None:
                    reward += sr.reward_delta
                    state = sr.state
    return ClosedLoopResult(
        total_reward=reward,
        steps=steps,
        completed=state.completed,
        model_inconsistent=state.model_inconsistent,
        log=log,
        notes=tuple(notes),
    )
