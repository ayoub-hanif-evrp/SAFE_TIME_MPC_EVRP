"""Decision-relevant dual MPC solver with optional bound pruning."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.bounds import evaluate_bound
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _first_travel_actions_single,
    _robust_continuation_ok,
    initial_state_single,
)
from safe_time_evrp.dr_dual.network import RoadNetwork, make_single_ev_corridors
from safe_time_evrp.dr_dual.transition import apply_action


@dataclass
class PruningStats:
    actions_generated: int = 0
    actions_ruled_out_by_safety: int = 0
    actions_pruned_by_bound: int = 0
    actions_expanded: int = 0
    observation_branches_evaluated: int = 0
    solver_seconds: float = 0.0
    incumbent_lower_bound: float | None = None
    selected_action: str | None = None
    selected_value: float | None = None
    used_pruning: bool = False
    notes: list[str] = field(default_factory=list)


def solve_dr_dual(
    net: RoadNetwork | None = None,
    *,
    use_pruning: bool = True,
    use_generic_clairvoyant_bound: bool = False,
    noise: float = 0.0,
) -> PruningStats:
    """Safe dual first-action optimization with optional DRUB pruning.

    Incumbent lower bound L: best fully evaluated safe action value so far
    (and initialized by best robust/passive score among safe actions).
    """
    net = net or make_single_ev_corridors()
    state = initial_state_single(net)
    stats = PruningStats(used_pruning=use_pruning)
    t0 = perf_counter()

    candidates = _first_travel_actions_single(net, state)
    stats.actions_generated = len(candidates)

    # Safety filter
    safe_actions: list[Action] = []
    for a in candidates:
        ok = True
        for theta in state.belief.support_set():
            tr = apply_action(net, state, a, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None or not _robust_continuation_ok(net, tr.state):
                ok = False
                break
        if ok:
            safe_actions.append(a)
        else:
            stats.actions_ruled_out_by_safety += 1

    # Initialize incumbent L from optimized passive (robust score)
    L = float("-inf")
    for a in safe_actions:
        # robust score via bound's robust_continuation_value
        b = evaluate_bound(net, state, a, noise=noise)
        if b is None:
            continue
        if b.robust_continuation_value > L:
            L = b.robust_continuation_value
    stats.incumbent_lower_bound = L if L > float("-inf") else None

    # Order: evaluate lower-info actions first to raise L before informative ones
    def info_key(a: Action) -> float:
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        return abs(seg.informative)

    safe_actions = sorted(safe_actions, key=info_key)

    best_val = float("-inf")
    best_key = None
    for a in safe_actions:
        b = evaluate_bound(net, state, a, noise=noise)
        if b is None:
            continue
        q_bar = b.q_bar
        if use_generic_clairvoyant_bound:
            # Ablation: same DRUB formula (already clairvoyant-after-theta); flag only
            stats.notes.append("generic_flag_same_construction")
        if use_pruning and L > float("-inf") and q_bar <= L + 1e-12:
            # Also require zero_voi or strictly dominated travel for aggressive prune
            # Sound prune: q_bar <= L implies cannot beat incumbent
            stats.actions_pruned_by_bound += 1
            stats.notes.append(f"pruned:{a.key()}:q_bar={q_bar:.4f}<=L={L:.4f}")
            continue
        # Expand: compute true Bayes value (same as exact oracle)
        val = _bayes_value_after_first(net, state, a, mode="safe_dual", noise=noise)
        stats.actions_expanded += 1
        stats.observation_branches_evaluated += len(state.belief.support)
        if val is None:
            continue
        if val > L:
            L = val
            stats.incumbent_lower_bound = L
        if val > best_val:
            best_val = val
            best_key = a.key()

    stats.selected_action = best_key
    stats.selected_value = best_val if best_key else None
    stats.solver_seconds = perf_counter() - t0
    return stats


def solve_info_gain_heuristic(net: RoadNetwork | None = None, *, noise: float = 0.0) -> PruningStats:
    """Unsafe-for-research baseline: pick safe action maximizing |informative| coefficient."""
    net = net or make_single_ev_corridors()
    state = initial_state_single(net)
    stats = PruningStats(used_pruning=False, notes=["info_gain_heuristic"])
    t0 = perf_counter()
    best = None
    best_info = -1.0
    for a in _first_travel_actions_single(net, state):
        stats.actions_generated += 1
        ok = True
        for theta in state.belief.support_set():
            tr = apply_action(net, state, a, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None or not _robust_continuation_ok(net, tr.state):
                ok = False
                break
        if not ok:
            stats.actions_ruled_out_by_safety += 1
            continue
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        if abs(seg.informative) > best_info:
            best_info = abs(seg.informative)
            best = a
    if best is not None:
        val = _bayes_value_after_first(net, state, best, mode="safe_dual", noise=noise)
        stats.selected_action = best.key()
        stats.selected_value = val
        stats.actions_expanded = 1
    stats.solver_seconds = perf_counter() - t0
    return stats


def solve_robust_no_learning(net: RoadNetwork | None = None, *, noise: float = 0.0) -> PruningStats:
    """Robust MPC: maximize min_θ continuation; ignore belief updates in scoring."""
    net = net or make_single_ev_corridors()
    state = initial_state_single(net)
    stats = PruningStats(notes=["robust_no_learning"])
    t0 = perf_counter()
    best_key = None
    best_score = float("-inf")
    for a in _first_travel_actions_single(net, state):
        stats.actions_generated += 1
        b = evaluate_bound(net, state, a, noise=noise)
        if b is None:
            stats.actions_ruled_out_by_safety += 1
            continue
        if b.robust_continuation_value > best_score:
            best_score = b.robust_continuation_value
            best_key = a.key()
        stats.actions_expanded += 1
    stats.selected_action = best_key
    stats.selected_value = best_score if best_key else None
    stats.solver_seconds = perf_counter() - t0
    return stats
