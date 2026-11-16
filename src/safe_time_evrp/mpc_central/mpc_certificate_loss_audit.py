"""Audit CERTIFIED_FEASIBILITY_LOST episodes with decision-level loss_events."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "experiments" / "MPC_CERTIFICATE_LOSS_AUDIT.md"

# Known LOST cells from prior development JSON (CSS-MPC).
LOST_CELLS = [
    ("c106C15", 1),
    ("r103C10", 0),
    ("r105C15", 0),
]


def audit_cell(stem: str, ridx: int, *, arrival, finite) -> dict:
    env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
    pol = policy_seed_for(stem, ridx, "shared")
    episode, _, _ = build_dynamic_episode_v2(
        stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
    )
    case = episode.case
    ctrl = CommitmentSafeStochasticMpc(
        case.instance,
        case.horizon,
        forecast=arrival,
        finite_demand_model=finite,
        n_scenarios=2,
        use_forecast=True,
        use_finite_demand=True,
        require_terminal_commitment=True,
        alns_iterations=10,
        time_limit_seconds=0.35,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=100,
    )
    result = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    losses = list(ctrl.profile.loss_events)
    first = losses[0] if losses else None
    return {
        "stem": stem,
        "realization_index": ridx,
        "environment_seed": env,
        "final_status": ctrl.last_validation_status,
        "n_loss_events": len(losses),
        "first_loss": first,
        "all_losses": losses,
        "completed": sum(1 for st in result.final_requests.values() if st == "completed"),
        "accepted_unfulfilled": sum(1 for st in result.final_requests.values() if st == "accepted_unfulfilled"),
        "interpretation": (
            "Fallback could not revalidate existing obligations after certificate advance/invalidation "
            "or scored-set exhaustion; status CERTIFIED_FEASIBILITY_LOST is an assumption-failure "
            "signal, not RF preservation."
            if losses
            else "No loss_events recorded this replay (nondeterministic wall-clock may differ)."
        ),
    }


def main() -> dict:
    splits = stratified_split_small()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    rows = [audit_cell(stem, ridx, arrival=arrival, finite=finite) for stem, ridx in LOST_CELLS]
    lines = [
        "# MPC certificate-loss audit",
        "",
        "Replayed development cells that previously ended in `CERTIFIED_FEASIBILITY_LOST`.",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(rows, indent=2),
        "```",
        "",
        "## Scientific reading",
        "",
        "- Loss means **no independently validated backup** for outstanding accepted customers.",
        "- This falsifies unconditional recursive feasibility of the viable set.",
        "- The controller correctly refuses `CERTIFIED_FEASIBLE` (certified-emission soundness).",
        "- See weakened theorem in `docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return {"rows": rows}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
