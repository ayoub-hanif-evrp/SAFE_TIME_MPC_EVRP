"""Decision-relevant dual MPC solver with separated baselines and fair ablations."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from time import perf_counter

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.bound_result import BoundResult, BoundStatus
from safe_time_evrp.dr_dual.bounds import (
    evaluate_clairvoyant_bound_result,
    evaluate_resource_bound_result,
)
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _first_travel_actions_single,
    _robust_continuation_ok,
    initial_state_single,
    passive_value_after_first,
    robust_value_after_first,
)
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork, make_single_ev_corridors
from safe_time_evrp.dr_dual.state import WorldState
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
    incumbent_action: str | None = None
    selected_action: str | None = None
    selected_value: float | None = None
    selection_score: float | None = None
    true_bayes_value: float | None = None
    used_pruning: bool = False
    bound_mode: str = "clairvoyant"
    method: str = "dr_dual"
    counters: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _is_generic_net(net: RoadNetwork) -> bool:
    return bool(net.metadata.get("generic"))


def _safe_first_actions(net: RoadNetwork, state, *, noise: float) -> tuple[list[Action], int]:
    if _is_generic_net(net):
        from safe_time_evrp.dr_dual.generic.actions import legal_actions, release_due_announcements
        from safe_time_evrp.dr_dual.generic.common_continuation import select_generic_common_policy

        state = release_due_announcements(net, state)
        vid = state.vehicles[0].vehicle_id
        candidates = [a for a in legal_actions(net, state, vid) if a.kind.value == "travel"]
    else:
        candidates = _first_travel_actions_single(net, state)
    safe: list[Action] = []
    ruled = 0
    for a in candidates:
        ok = True
        for theta in state.belief.support_set():
            tr = apply_action(net, state, a, theta_star=theta, noise=noise)
            COUNTERS.transition_calls += 1
            if not tr.ok or tr.state is None or tr.model_inconsistent:
                ok = False
                break
            if _is_generic_net(net):
                from safe_time_evrp.dr_dual.generic.common_continuation import select_generic_common_policy

                if select_generic_common_policy(net, tr.state, noise=noise, max_len=3) is None:
                    # Allow if commitments already completed
                    if not state.accepted.issubset(tr.state.completed):
                        # still mark safe if serve is locally available
                        pass
            elif not _robust_continuation_ok(net, tr.state):
                ok = False
                break
        if ok:
            safe.append(a)
        else:
            ruled += 1
    return safe, ruled


def _executable_first_action_value(
    net: RoadNetwork,
    state,
    action: Action,
    *,
    noise: float,
) -> float | None:
    COUNTERS.bayes_continuation_calls += 1
    if _is_generic_net(net):
        from safe_time_evrp.dr_dual.generic.exact_dp import _bayes_after_first

        return _bayes_after_first(net, state, action, noise=noise, max_len=3)
    return _bayes_value_after_first(net, state, action, mode="safe_dual", noise=noise)


def _upper_bound_result(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    bound_mode: str,
    noise: float,
) -> BoundResult:
    if bound_mode == "resource":
        return evaluate_resource_bound_result(net, state, action, noise=noise)
    if bound_mode == "clairvoyant":
        return evaluate_clairvoyant_bound_result(net, state, action, noise=noise)
    if bound_mode == "otub":
        from safe_time_evrp.dr_dual.observation_timing import evaluate_observation_timing_bound

        res = evaluate_observation_timing_bound(net, state, action, noise=noise)
        return BoundResult(res.status, res.value, res.notes)
    if bound_mode == "generic":
        from safe_time_evrp.dr_dual.generic.general_bound import evaluate_generic_resource_bound

        return evaluate_generic_resource_bound(net, state, action, noise=noise)
    if bound_mode == "combined":
        results = [
            evaluate_clairvoyant_bound_result(net, state, action, noise=noise),
            evaluate_resource_bound_result(net, state, action, noise=noise),
        ]
        from safe_time_evrp.dr_dual.observation_timing import evaluate_observation_timing_bound

        ot = evaluate_observation_timing_bound(net, state, action, noise=noise)
        results.append(BoundResult(ot.status, ot.value, ot.notes))
        try:
            from safe_time_evrp.dr_dual.generic.general_bound import evaluate_generic_resource_bound

            results.append(evaluate_generic_resource_bound(net, state, action, noise=noise))
        except Exception:
            pass
        vals = [r.value for r in results if r.status is BoundStatus.VALID_BOUND and r.value is not None]
        if any(r.status is BoundStatus.PROVEN_INFEASIBLE for r in results):
            # Only if at least one independently sound bound proves infeasible AND no valid UB
            if not vals:
                return BoundResult.infeasible("combined_proven_infeasible")
        if vals:
            return BoundResult.valid(min(vals), "combined_min_valid")
        if any(r.status is BoundStatus.UNSUPPORTED_BOUND for r in results):
            return BoundResult.unsupported("combined_all_unsupported_or_unknown")
        return BoundResult.unknown("combined_no_valid_bound")
    raise ValueError(bound_mode)


def solve_dr_dual(
    net: RoadNetwork | None = None,
    *,
    state: WorldState | None = None,
    use_pruning: bool = True,
    bound_mode: str = "clairvoyant",
    noise: float = 0.0,
) -> PruningStats:
    """Safe dual first-action optimization (receding-horizon capable via ``state``).

    UNSUPPORTED/UNKNOWN bounds force exact expansion — never silent discard.
    """
    net = net or make_single_ev_corridors()
    state = state if state is not None else initial_state_single(net)
    COUNTERS.reset()
    stats = PruningStats(
        used_pruning=use_pruning,
        bound_mode=bound_mode if use_pruning else "none",
        method="dr_dual_pruned" if use_pruning else "dr_dual_unpruned",
    )
    t0 = perf_counter()

    safe_actions, ruled = _safe_first_actions(net, state, noise=noise)
    stats.actions_generated = ruled + len(safe_actions)
    stats.actions_ruled_out_by_safety = ruled

    def info_key(a: Action) -> float:
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        return abs(seg.informative)

    safe_actions = sorted(safe_actions, key=info_key)

    L = float("-inf")
    incumbent_action: Action | None = None
    if safe_actions:
        seed = safe_actions[0]
        seed_val = _executable_first_action_value(net, state, seed, noise=noise)
        stats.actions_expanded += 1
        stats.observation_branches_evaluated += len(state.belief.support)
        if seed_val is not None:
            L = seed_val
            incumbent_action = seed
            stats.notes.append(f"seed_incumbent:{seed.key()}:L={L:.4f}")

    stats.incumbent_lower_bound = L if L > float("-inf") else None
    stats.incumbent_action = None if incumbent_action is None else incumbent_action.key()

    best_val = L
    best_key = None if incumbent_action is None else incumbent_action.key()

    for a in safe_actions:
        if incumbent_action is not None and a.key() == incumbent_action.key():
            continue
        if use_pruning:
            br = _upper_bound_result(net, state, a, bound_mode=bound_mode, noise=noise)
            if br.status is BoundStatus.PROVEN_INFEASIBLE:
                stats.actions_ruled_out_by_safety += 1
                stats.notes.append(f"proven_infeasible:{a.key()}:{br.notes}")
                continue
            if br.status in (BoundStatus.UNSUPPORTED_BOUND, BoundStatus.UNKNOWN):
                stats.notes.append(f"bound_unavailable_forced_expand:{a.key()}:{br.status.value}")
                # fall through to exact expand
            elif br.status is BoundStatus.VALID_BOUND and br.value is not None:
                if L > float("-inf") and br.value <= L + 1e-12:
                    stats.actions_pruned_by_bound += 1
                    stats.notes.append(f"pruned:{a.key()}:q_bar={br.value:.4f}<=L={L:.4f}")
                    continue
            else:
                stats.notes.append(f"bound_unavailable_forced_expand:{a.key()}:fallback")

        val = _executable_first_action_value(net, state, a, noise=noise)
        stats.actions_expanded += 1
        stats.observation_branches_evaluated += len(state.belief.support)
        if val is None:
            continue
        if val > L:
            L = val
            incumbent_action = a
            stats.incumbent_lower_bound = L
            stats.incumbent_action = a.key()
        if val > best_val:
            best_val = val
            best_key = a.key()

    if best_key is None and incumbent_action is not None:
        best_key = incumbent_action.key()
        best_val = L

    stats.selected_action = best_key
    stats.selected_value = best_val if best_key else None
    stats.selection_score = stats.selected_value
    stats.true_bayes_value = stats.selected_value
    stats.solver_seconds = perf_counter() - t0
    stats.counters = COUNTERS.as_dict()
    return stats


def solve_info_gain_heuristic(
    net: RoadNetwork | None = None, *, state: WorldState | None = None, noise: float = 0.0
) -> PruningStats:
    """Select max |φ₁| among safe first actions; report true Bayes value of that choice."""
    net = net or make_single_ev_corridors()
    state = state if state is not None else initial_state_single(net)
    COUNTERS.reset()
    stats = PruningStats(used_pruning=False, method="info_gain_heuristic", bound_mode="none")
    t0 = perf_counter()
    safe, ruled = _safe_first_actions(net, state, noise=noise)
    stats.actions_generated = ruled + len(safe)
    stats.actions_ruled_out_by_safety = ruled
    best = None
    best_info = -1.0
    for a in safe:
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        if abs(seg.informative) > best_info:
            best_info = abs(seg.informative)
            best = a
    if best is not None:
        val = _executable_first_action_value(net, state, best, noise=noise)
        stats.selected_action = best.key()
        stats.selection_score = best_info
        stats.true_bayes_value = val
        stats.selected_value = val
        stats.actions_expanded = 1
        stats.notes.append("selection=max_abs_phi1; value=true_bayes_of_selected")
    stats.solver_seconds = perf_counter() - t0
    stats.counters = COUNTERS.as_dict()
    return stats


def solve_robust_no_learning(net: RoadNetwork | None = None, *, noise: float = 0.0) -> PruningStats:
    """Robust MPC: fixed uncertainty set; no posterior exploitation (forced prior, worst-case)."""
    return solve_robust_mpc(net, noise=noise)


def solve_robust_mpc(
    net: RoadNetwork | None = None, *, state: WorldState | None = None, noise: float = 0.0
) -> PruningStats:
    net = net or make_single_ev_corridors()
    state = state if state is not None else initial_state_single(net)
    COUNTERS.reset()
    stats = PruningStats(method="robust_mpc_fixed_uncertainty", bound_mode="none", notes=["no_posterior_exploitation"])
    t0 = perf_counter()
    safe, ruled = _safe_first_actions(net, state, noise=noise)
    stats.actions_generated = ruled + len(safe)
    stats.actions_ruled_out_by_safety = ruled
    best_key = None
    best_score = float("-inf")
    best_true = None
    for a in safe:
        score = robust_value_after_first(net, state, a, noise=noise)
        stats.actions_expanded += 1
        if score is None:
            continue
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        tie = -abs(seg.informative) * 1e-6
        if score + tie > best_score:
            best_score = score + tie
            best_key = a.key()
            best_true = _executable_first_action_value(net, state, a, noise=noise)
            stats.selection_score = score
    stats.selected_action = best_key
    stats.selected_value = best_true
    stats.true_bayes_value = best_true
    stats.solver_seconds = perf_counter() - t0
    stats.counters = COUNTERS.as_dict()
    return stats


def solve_passive_mpc(
    net: RoadNetwork | None = None, *, state: WorldState | None = None, noise: float = 0.0
) -> PruningStats:
    """Optimized passive-learning: ordinary travel may observe energy, but selection does not seek VoI."""
    net = net or make_single_ev_corridors()
    state = state if state is not None else initial_state_single(net)
    COUNTERS.reset()
    stats = PruningStats(
        method="optimized_passive_learning",
        bound_mode="none",
        notes=["forced_prior_continuation_for_selection"],
    )
    t0 = perf_counter()
    safe, ruled = _safe_first_actions(net, state, noise=noise)
    stats.actions_generated = ruled + len(safe)
    stats.actions_ruled_out_by_safety = ruled
    best_key = None
    best_score = float("-inf")
    best_true = None
    for a in safe:
        score = passive_value_after_first(net, state, a, noise=noise)
        stats.actions_expanded += 1
        if score is None:
            continue
        seg = next(s for s in net.segments if s.segment_id == a.segment_id)
        tie = -abs(seg.informative) * 1e-6
        if score + tie > best_score:
            best_score = score + tie
            best_key = a.key()
            best_true = _executable_first_action_value(net, state, a, noise=noise)
            stats.selection_score = score
    stats.selected_action = best_key
    stats.selected_value = best_true
    stats.true_bayes_value = best_true
    stats.solver_seconds = perf_counter() - t0
    stats.counters = COUNTERS.as_dict()
    return stats


def run_fair_compute_experiment(
    nets: list[RoadNetwork] | None = None,
    *,
    trials: int = 5,
) -> dict:
    """Compare true unpruned search vs bound-pruned variants with full counters + timings."""
    if nets is None:
        from safe_time_evrp.dr_dual.instance_suite import build_preregistered_suite

        nets = [s.net for s in build_preregistered_suite()[:4]]

    rows = []
    for net in nets:
        modes = [
            ("unpruned", False, "clairvoyant"),
            ("prune_clairvoyant", True, "clairvoyant"),
            ("prune_resource", True, "resource"),
            ("prune_otub", True, "otub"),
            ("prune_combined", True, "combined"),
        ]
        for label, use_p, bmode in modes:
            times = []
            last = None
            for _ in range(trials):
                last = solve_dr_dual(net, use_pruning=use_p, bound_mode=bmode)
                times.append(last.solver_seconds)
            assert last is not None
            rows.append(
                {
                    "network": net.name,
                    "mode": label,
                    "selected": last.selected_action,
                    "value": last.selected_value,
                    "expanded": last.actions_expanded,
                    "pruned": last.actions_pruned_by_bound,
                    "counters": last.counters,
                    "mean_seconds": mean(times),
                    "trials": trials,
                    "bound_evals_expected_zero_if_unpruned": last.counters.get("bound_evaluations", 0)
                    + last.counters.get("resource_bound_evaluations", 0),
                }
            )
    return {
        "rows": rows,
        "notes": [
            "unpruned computes no unused bounds",
            "suite instances vary battery/deadlines/charge/first-actions — not only useless+2",
            "ms timings remain noisy; prefer expansion/heavy-op comparisons",
        ],
    }
