"""Stage 1B: diagnose first trajectory divergence (inspected instances only).

``c208C15`` (env=1410663356, pol=595457899) is **inspected** final-test data.
Use for correctness diagnosis only — never for parameter tuning.
"""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import build_dynamic_episode_v2
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey

# Inspected cell from FINAL_COMPETITIVE_COMPARISON.json — do not retune on this.
C208_STEM = "c208C15"
C208_ENV = 1410663356
C208_POL = 595457899
ALNS_ITER = 10
ALNS_TIME = 0.35


def _keys(decision) -> dict:
    k = FirstActionKey.from_decision(decision)
    return {
        "newly_accepted": list(k.newly_accepted),
        "rejected": list(k.rejected),
        "first_legs": [list(x) for x in k.first_legs],
        "notes_head": list(decision.notes)[:12],
    }


def first_divergence_walk(
    *,
    stem: str = C208_STEM,
    environment_seed: int = C208_ENV,
    policy_seed: int = C208_POL,
    max_epochs: int = 40,
) -> dict:
    """Walk two sims with shared releases; log first FirstActionKey mismatch."""
    splits = stratified_split_small()
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"][:3]])
    episode, _cls, _fleet = build_dynamic_episode_v2(
        stem,
        environment_seed=environment_seed,
        policy_seed=policy_seed,
        dynamicity="medium",
        split="test",
    )
    case = episode.case

    def _ctrl_gn(*, equivalence_mode: bool = False):
        # Equivalence uses iteration-primary budgets to remove wall-clock races.
        tlim = 1e9 if equivalence_mode else ALNS_TIME
        return CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=arrival,
            n_scenarios=2,
            alns_iterations=ALNS_ITER,
            time_limit_seconds=tlim,
            seed=policy_seed,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="greedy_nominal",
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=120,
        )

    def _ctrl_bap(*, allow_override: bool, equivalence_mode: bool = False):
        return BaselineAnchoredPredictiveCCE(
            case.instance,
            case.horizon,
            forecast=arrival,
            finite_model=finite,
            n_scenarios=2,
            alns_iterations=ALNS_ITER,
            time_limit_seconds=ALNS_TIME,
            seed=policy_seed,
            use_finite_demand=True,
            allow_override=allow_override,
            equivalence_mode=equivalence_mode,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=120,
        )

    # Compare zero-override BAP vs standalone GN on shared plant walk.
    sim_a = FleetSimulator(case.instance, case.fleet_size)
    sim_b = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim_a.schedule_release(cid, t)
        sim_b.schedule_release(cid, t)
    gn = _ctrl_gn(equivalence_mode=True)
    zo = _ctrl_bap(allow_override=False, equivalence_mode=True)
    epochs = []
    diverge_zo = None
    replan_a = replan_b = None
    for epoch in range(max_epochs):
        while True:
            # Placeholder: decisions fire at initial / replan epochs below.
            break
        obs_a = sim_a.observation()
        obs_b = sim_b.observation()
        # Align time: if clocks differ, report and stop.
        if abs(obs_a.time - obs_b.time) > 1e-9:
            diverge_zo = {
                "epoch": epoch,
                "reason": "clock_desync",
                "time_a": obs_a.time,
                "time_b": obs_b.time,
            }
            break
        trigger = "initial" if epoch == 0 else "replan_interval"
        if epoch == 0:
            # Drain time-0 releases
            for sim in (sim_a, sim_b):
                while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
                    sim.pop_event()
            obs_a = sim_a.observation()
            obs_b = sim_b.observation()
            trigger = "initial"
        da = gn.decide(obs_a, trigger)
        db = zo.decide(obs_b, trigger)
        ka, kb = FirstActionKey.from_decision(da), FirstActionKey.from_decision(db)
        row = {
            "epoch": epoch,
            "time": obs_a.time,
            "trigger": trigger,
            "gn": _keys(da),
            "bap_zero_override": _keys(db),
            "match": ka == kb,
        }
        epochs.append(row)
        if ka != kb and diverge_zo is None:
            diverge_zo = {
                "epoch": epoch,
                "time": obs_a.time,
                "cause_hypothesis": (
                    "Independent-trajectory mismatch under matched budget/seed. "
                    "If closed-loop completed counts still match, residual ALNS "
                    "nondeterminism may affect accepts without changing finals."
                ),
                "gn": row["gn"],
                "bap_zero_override": row["bap_zero_override"],
            }
            break
        # Advance each plant with *its own* decision (true independent trajectories).
        sim_a.apply_decision(da)
        sim_b.apply_decision(db)
        if replan_a is not None:
            sim_a.cancel(replan_a)
        if replan_b is not None:
            sim_b.cancel(replan_b)
        replan_a = sim_a.schedule_replan(sim_a.time + case.max_replan_interval)
        replan_b = sim_b.schedule_replan(sim_b.time + case.max_replan_interval)
        # Step one event on both
        for sim in (sim_a, sim_b):
            nxt = sim.next_event_time()
            if nxt is None or nxt > case.t_max:
                return {
                    "stem": stem,
                    "inspected": True,
                    "zero_override_vs_gn": {
                        "first_divergence": diverge_zo,
                        "epochs_compared": len(epochs),
                        "all_matched": diverge_zo is None,
                    },
                }
            sim.pop_event()

    # Closed-loop completed counts (diagnostic only).
    def _closed(name, ctrl):
        res = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
        )
        final = res.final_requests
        return {
            "controller": name,
            "completed": sum(1 for st in final.values() if st == "completed"),
            "au": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
            "rejected": sum(1 for st in final.values() if st == "rejected"),
            "termination_reason": res.termination_reason,
            "fallback_count": res.fallback_count,
        }

    closed_eq = {
        "cce_greedy_nominal_iter": _closed("cce_greedy_nominal_iter", _ctrl_gn(equivalence_mode=True)),
        "bap_zero_override_iter": _closed(
            "bap_zero_override_iter", _ctrl_bap(allow_override=False, equivalence_mode=True)
        ),
    }
    closed_wall = {
        "cce_greedy_nominal_0_35s": _closed("cce_greedy_nominal_0_35s", _ctrl_gn(equivalence_mode=False)),
        "bap_allow_override_0_35s": _closed(
            "bap_allow_override_0_35s", _ctrl_bap(allow_override=True, equivalence_mode=False)
        ),
    }
    return {
        "stem": stem,
        "environment_seed": environment_seed,
        "policy_seed": policy_seed,
        "inspected_final_test_cell": True,
        "warning": "Do not tune parameters on this instance.",
        "root_cause_pre_fix": (
            "BAP nested incumbent used time_limit*0.45 and a separate CertificateStore; "
            "cooperative wall-clock ALNS cutoffs amplify trajectory variance. "
            "Stage-1A matches incumbent budget, shares the store, and adds "
            "allow_override=False / equivalence_mode (iteration-primary) for deterministic checks."
        ),
        "zero_override_vs_gn": {
            "first_divergence": diverge_zo,
            "epochs_compared": len(epochs),
            "all_matched": diverge_zo is None,
            "epochs": epochs[:12],
        },
        "closed_loop_iteration_primary": closed_eq,
        "closed_loop_wall_clock_0_35s": closed_wall,
        "interpretation": (
            "Iteration-primary zero-override must match GN completed/AU. "
            "Wall-clock 0.35s runs remain cooperative (not hard-real-time) and may differ."
        ),
    }


def main() -> None:
    out = Path("docs/experiments/BAP_C208C15_DIVERGENCE_AUDIT.md")
    payload = first_divergence_walk()
    lines = [
        "# BAP divergence audit — `c208C15` (inspected)",
        "",
        f"**Environment seed:** `{payload['environment_seed']}`  ",
        f"**Policy seed:** `{payload['policy_seed']}`  ",
        "",
        "> Inspected final-test cell. Correctness diagnosis only — **no parameter tuning**.",
        "",
        "## Root cause (pre-fix)",
        "",
        payload["root_cause_pre_fix"],
        "",
        "## Closed-loop (iteration-primary equivalence)",
        "",
        f"```json\n{json.dumps(payload['closed_loop_iteration_primary'], indent=2)}\n```",
        "",
        "## Closed-loop (cooperative 0.35s wall clock)",
        "",
        f"```json\n{json.dumps(payload['closed_loop_wall_clock_0_35s'], indent=2)}\n```",
        "",
        "## Zero-override vs greedy-nominal first-action walk",
        "",
        f"- Epochs compared: {payload['zero_override_vs_gn']['epochs_compared']}",
        f"- All matched: **{payload['zero_override_vs_gn']['all_matched']}**",
        f"- First divergence: `{payload['zero_override_vs_gn']['first_divergence']}`",
        "",
        payload["interpretation"],
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    Path("docs/experiments/BAP_C208C15_DIVERGENCE_AUDIT.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "iter_primary": payload["closed_loop_iteration_primary"],
                "wall_0_35": payload["closed_loop_wall_clock_0_35s"],
                "zo_walk_matched": payload["zero_override_vs_gn"]["all_matched"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
