"""Reproducible diagnostics for discriminating scenarios D1–D4."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from safe_time_evrp.dr_dual.generic.common_continuation import realize_plan, select_generic_common_policy
from safe_time_evrp.dr_dual.generic.discriminating_suite import DiscInstance, build_discriminating_suite
from safe_time_evrp.dr_dual.generic.exact_dp import _first_actions, solve_generic_exact
from safe_time_evrp.dr_dual.generic.model import initial_generic_state
from safe_time_evrp.dr_dual.generic.policy_class import RESTRICTED_CONTINUATION_MAX_LEN
from safe_time_evrp.dr_dual.replay import replay_plant_log_independent
from safe_time_evrp.dr_dual.solver import solve_dr_dual
from safe_time_evrp.dr_dual.state import PlantLog
from safe_time_evrp.dr_dual.transition import apply_action


@dataclass
class ScenarioDiag:
    instance_id: str
    tags: list[str]
    expected_traits: list[str]
    first_action_set: list[str]
    exact_first: str | None
    exact_value: float | None
    exact_status: str
    unpruned_first: str | None
    unpruned_value: float | None
    generic_first: str | None
    generic_value: float | None
    agrees_unpruned: bool
    agrees_generic: bool
    disagreement_cause: str
    trajectory_ok_theta0: bool
    trajectory_ok_theta1: bool
    trajectory_notes: list[str]
    policy_class: str


def _cause(exact_first, unpruned_first, exact_value, unpruned_value, firsts_exact, firsts_solver) -> str:
    if exact_first == unpruned_first and (
        exact_value is None or unpruned_value is None or abs((exact_value or 0) - (unpruned_value or 0)) < 1e-6
    ):
        return "none"
    if set(firsts_exact) != set(firsts_solver):
        return "different_first_action_sets"
    if unpruned_first is None and exact_first is not None:
        return "solver_no_executable_value_under_declared_horizon"
    if exact_first != unpruned_first:
        return "different_optimum_or_horizon_mismatch"
    return "value_mismatch_same_action"


def _verify_trajectory(inst: DiscInstance, first_key: str | None) -> tuple[bool, bool, list[str]]:
    notes: list[str] = []
    if first_key is None:
        return False, False, ["no_first_action"]
    net = inst.net
    state0 = initial_generic_state(net)
    first = next((a for a in _first_actions(net, state0) if a.key() == first_key), None)
    if first is None:
        return False, False, ["first_not_in_action_set"]

    oks: list[bool] = []
    for theta in (0.0, 1.0):
        log = PlantLog()
        tr = apply_action(net, state0, first, theta_star=theta, noise=0.0)
        if not tr.ok or tr.state is None:
            notes.append(f"theta={theta}:first_travel_failed")
            oks.append(False)
            continue
        if first.segment_id:
            seg = next(s for s in net.segments if s.segment_id == first.segment_id)
            vv = tr.state.vehicle(first.vehicle_id)
            log.record(
                kind="travel",
                vehicle=first.vehicle_id,
                segment=first.segment_id,
                origin=seg.origin,
                destination=seg.destination,
                energy=net.energy(seg, theta),
                theta_star=theta,
                time=vv.time,
                soc=vv.soc,
            )
        common = select_generic_common_policy(net, tr.state, noise=0.0)
        if common is None:
            notes.append(f"theta={theta}:no_common_continuation")
            oks.append(False)
            continue
        reward = realize_plan(net, tr.state, list(common[0]), theta, noise=0.0)
        if reward is None:
            notes.append(f"theta={theta}:realize_failed")
            oks.append(False)
            continue
        # Replay first travel physically
        start = net.metadata.get("start_nodes", {}).get(first.vehicle_id, net.depot)
        rep = replay_plant_log_independent(net, log, initial_soc=net.battery, initial_node=start)
        if not rep.ok:
            notes.append(f"theta={theta}:replay_reject:{rep.reason}")
            oks.append(False)
            continue
        notes.append(f"theta={theta}:ok_cont_reward={reward:.4f}_plan_len={len(common[0])}")
        oks.append(True)
    return (oks[0] if oks else False), (oks[1] if len(oks) > 1 else False), notes


def diagnose_scenario(inst: DiscInstance) -> ScenarioDiag:
    net = inst.net
    state = initial_generic_state(net)
    firsts = [a.key() for a in _first_actions(net, state)]
    exact = solve_generic_exact(net, max_len=RESTRICTED_CONTINUATION_MAX_LEN)
    unp = solve_dr_dual(net, state=state, use_pruning=False, bound_mode="clairvoyant")
    gen = solve_dr_dual(net, state=state, use_pruning=True, bound_mode="generic")
    # Solver first-set (same helper path)
    from safe_time_evrp.dr_dual.solver import _safe_first_actions

    safe, _ = _safe_first_actions(net, state, noise=0.0)
    solver_firsts = [a.key() for a in safe]
    cause = _cause(
        exact.first_action_key,
        unp.selected_action,
        exact.value,
        unp.selected_value,
        firsts,
        solver_firsts,
    )
    t0, t1, tnotes = _verify_trajectory(inst, exact.first_action_key)
    return ScenarioDiag(
        instance_id=inst.instance_id,
        tags=list(inst.tags),
        expected_traits=list(inst.expected_traits),
        first_action_set=firsts,
        exact_first=exact.first_action_key,
        exact_value=exact.value,
        exact_status=exact.status.value,
        unpruned_first=unp.selected_action,
        unpruned_value=unp.selected_value,
        generic_first=gen.selected_action,
        generic_value=gen.selected_value,
        agrees_unpruned=exact.first_action_key == unp.selected_action
        and exact.value is not None
        and unp.selected_value is not None
        and abs(exact.value - unp.selected_value) < 1e-6,
        agrees_generic=exact.first_action_key == gen.selected_action
        and exact.value is not None
        and gen.selected_value is not None
        and abs(exact.value - gen.selected_value) < 1e-6,
        disagreement_cause=cause,
        trajectory_ok_theta0=t0,
        trajectory_ok_theta1=t1,
        trajectory_notes=tnotes,
        policy_class=f"first_fleet_travel+common_continuation_max_len={RESTRICTED_CONTINUATION_MAX_LEN}",
    )


def run_all_diagnostics() -> list[ScenarioDiag]:
    return [diagnose_scenario(inst) for inst in build_discriminating_suite()]


def write_diagnostics(out_dir: Path) -> dict:
    rows = run_all_diagnostics()
    payload = {
        "policy_class": f"first_fleet_travel+common_continuation_max_len={RESTRICTED_CONTINUATION_MAX_LEN}",
        "rows": [asdict(r) for r in rows],
        "summary": {
            "n": len(rows),
            "unpruned_agree": sum(1 for r in rows if r.agrees_unpruned),
            "generic_agree": sum(1 for r in rows if r.agrees_generic),
            "trajectories_ok": sum(1 for r in rows if r.trajectory_ok_theta0 and r.trajectory_ok_theta1),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scenario_diagnostics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_diagnostics(Path("docs/commitment_safe_mpc"))
    print(json.dumps(art["summary"], indent=2))
    for r in art["rows"]:
        print(
            r["instance_id"],
            "exact",
            r["exact_first"],
            r["exact_value"],
            "unp",
            r["unpruned_first"],
            "gen",
            r["generic_first"],
            "cause",
            r["disagreement_cause"],
            "traj",
            r["trajectory_ok_theta0"],
            r["trajectory_ok_theta1"],
        )
