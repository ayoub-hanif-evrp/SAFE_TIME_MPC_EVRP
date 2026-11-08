"""Counterexamples that invalidate the pre-repair generic TEI bound on the dynamic model."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.generic.actions import release_due_announcements
from safe_time_evrp.dr_dual.generic.model import initial_generic_state, make_tiny_generic_instance
from safe_time_evrp.dr_dual.state import PlantLog
from safe_time_evrp.dr_dual.transition import apply_action


def five_action_multi_customer_continuation() -> dict:
    """Serve C0, accept+serve later-announced C1, return to depot.

    Expected reward ≈ 14.625 under equal θ prior; old bound counted only C0 (≈9.85).
    """
    net = make_tiny_generic_instance(n_customers=3, n_vehicles=1)
    state0 = initial_generic_state(net)
    first = Action(ActionKind.TRAVEL, "v1", segment_id="D_N0_exploit")
    rewards = []
    logs = []
    for theta in (0.0, 1.0):
        log = PlantLog()
        s = state0
        total = 0.0
        plan = [
            first,
            Action(ActionKind.SERVE, "v1", customer_id="cust_0"),
            Action(ActionKind.TRAVEL, "v1", segment_id="N0_N1"),
            # Accept after announcement (time ≥ 2); fleet-level accept not requiring presence
            Action(ActionKind.ACCEPT, "v1", customer_id="cust_1"),
            Action(ActionKind.SERVE, "v1", customer_id="cust_1"),
            Action(ActionKind.TRAVEL, "v1", segment_id="N1_D"),
        ]
        ok = True
        for act in plan:
            s = release_due_announcements(net, s)
            # If accept before announce, wait until release
            if act.kind is ActionKind.ACCEPT and act.customer_id not in s.announced:
                release_t = float(net.metadata["announce_at"][act.customer_id])
                v = s.vehicle("v1")
                if v.time + 1e-12 < release_t:
                    w = apply_action(
                        net,
                        s,
                        Action(ActionKind.WAIT, "v1", wait_duration=release_t - v.time),
                        theta_star=theta,
                        log=log,
                    )
                    if not w.ok or w.state is None:
                        ok = False
                        break
                    total += w.reward_delta
                    s = w.state
                    s = release_due_announcements(net, s)
            tr = apply_action(net, s, act, theta_star=theta, log=log)
            if not tr.ok or tr.state is None:
                ok = False
                break
            total += tr.reward_delta
            s = tr.state
        if not ok:
            return {"ok": False, "note": "plan_failed", "theta": theta}
        if not {"cust_0", "cust_1"}.issubset(s.completed):
            return {"ok": False, "note": "customers_not_completed", "completed": sorted(s.completed)}
        if s.vehicle("v1").node != "D":
            return {"ok": False, "note": "no_depot_return", "node": s.vehicle("v1").node}
        rewards.append(total)
        logs.append(len(log.events))
    expected = 0.5 * sum(rewards)
    return {
        "ok": True,
        "per_theta_reward": {0.0: rewards[0], 1.0: rewards[1]},
        "expected_reward": expected,
        "approx_target": 14.625,
        "matches_audit": abs(expected - 14.625) < 0.05,
    }


def old_bound_undercounts_future_announcement() -> dict:
    """Reproduce: post-travel pending set omits cust_1 → bound < feasible continuation."""
    from safe_time_evrp.dr_dual.generic.general_bound import (
        evaluate_generic_resource_bound_legacy_unsafe,
        evaluate_trivial_safe_reward_bound,
    )

    net = make_tiny_generic_instance(n_customers=3, n_vehicles=1)
    state = initial_generic_state(net)
    first = Action(ActionKind.TRAVEL, "v1", segment_id="D_N0_exploit")
    cont = five_action_multi_customer_continuation()
    legacy = evaluate_generic_resource_bound_legacy_unsafe(net, state, first)
    trivial = evaluate_trivial_safe_reward_bound(net, state, first)
    return {
        "continuation": cont,
        "legacy_status": legacy.status.value,
        "legacy_value": legacy.value,
        "trivial_status": trivial.status.value,
        "trivial_value": trivial.value,
        "legacy_undercounts": (
            cont["ok"] and legacy.value is not None and legacy.value + 1e-9 < cont["expected_reward"]
        ),
        "trivial_dominates_continuation": (
            cont["ok"] and trivial.value is not None and trivial.value + 1e-9 >= cont["expected_reward"]
        ),
    }
