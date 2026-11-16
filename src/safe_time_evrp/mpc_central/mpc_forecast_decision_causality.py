"""Diagnose why forecast-enabled CSS-MPC can rank worse than empty-future."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.state import Decision
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey, generate_counterfactual_actions
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "experiments" / "MPC_FORECAST_DECISION_CAUSALITY.md"


def _score(inst, obs, cand, scenarios, horizon, energy=None):
    mean_v, scores = expected_rollout_value(
        inst,
        obs,
        cand,
        scenarios,
        horizon=horizon,
        max_scenarios=len(scenarios),
        scoring_mode="causal",
        max_replan_interval=5.0,
        max_events=80,
        energy=energy,
    )
    return mean_v, scores


def diagnose_epoch(inst, obs, horizon, finite, arrival, seed: int) -> dict | None:
    public = make_public_snapshot(inst, obs, horizon).instance
    cands, _ = generate_counterfactual_actions(
        inst,
        obs,
        horizon=horizon,
        alns_iterations=6,
        alns_time=0.15,
        seed=seed,
        include_solver_baselines=True,
        include_b1=True,
    )
    feasible = []
    for name, cand in cands:
        rep = validate_continuation(public, obs, cand.routes, require_new=frozenset(cand.newly_accepted))
        if rep.ok:
            feasible.append((name, cand))
    if len(feasible) < 2:
        return None

    empty = [[]]
    from safe_time_evrp.mpc3c.finite_demand_forecast import sample_finite_demand_scenarios

    forecast_sc = sample_finite_demand_scenarios(finite, obs, inst, horizon=horizon, n_scenarios=2, seed=seed)

    ranked_empty = []
    ranked_fc = []
    for name, cand in feasible:
        d = Decision(
            time=obs.time,
            routes=cand.routes,
            accepted=list(obs.accepted) + [c for c in cand.newly_accepted if c not in obs.accepted],
            newly_accepted=list(cand.newly_accepted),
            rejected=list(cand.rejected),
            deferred=list(cand.deferred),
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=list(cand.planned_service),
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=0.0,
            trigger="diag",
            locked_destinations={},
            notes=[],
        )
        ve, _ = _score(inst, obs, d, empty, horizon)
        vf, _ = _score(inst, obs, d, forecast_sc, horizon)
        key = FirstActionKey.from_decision(d)
        ranked_empty.append((ve, name, key.first_legs, tuple(d.newly_accepted)))
        ranked_fc.append((vf, name, key.first_legs, tuple(d.newly_accepted)))
    ranked_empty.sort(reverse=True)
    ranked_fc.sort(reverse=True)
    disagree = ranked_empty[0][2:] != ranked_fc[0][2:]
    return {
        "time": obs.time,
        "n_feasible": len(feasible),
        "empty_winner": {
            "name": ranked_empty[0][1],
            "value": ranked_empty[0][0],
            "legs": [list(x) for x in ranked_empty[0][2]],
            "newly": list(ranked_empty[0][3]),
        },
        "forecast_winner": {
            "name": ranked_fc[0][1],
            "value": ranked_fc[0][0],
            "legs": [list(x) for x in ranked_fc[0][2]],
            "newly": list(ranked_fc[0][3]),
        },
        "ranking_disagreement": disagree,
        "top3_empty": [{"name": n, "value": v, "legs": [list(x) for x in legs]} for v, n, legs, _ in ranked_empty[:3]],
        "top3_forecast": [{"name": n, "value": v, "legs": [list(x) for x in legs]} for v, n, legs, _ in ranked_fc[:3]],
    }


def main() -> dict:
    splits = stratified_split_small()
    # Development-only stems for diagnosis (not train).
    stems = [s for s in splits["development"] if s.endswith(("C5", "C10", "C15"))][:4]
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    audits = []
    closed = []
    for stem in stems:
        env = environment_seed_for(stem, 0) & 0x7FFFFFFF
        pol = policy_seed_for(stem, 0, "shared")
        episode, _, _ = build_dynamic_episode_v2(
            stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
        )
        case = episode.case
        # Closed-loop empty vs forecast on same episode for outcome gap.
        from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc

        common = dict(
            alns_iterations=8,
            time_limit_seconds=0.35,
            seed=pol,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=80,
            require_terminal_commitment=True,
        )
        outcomes = {}
        for label, kwargs in (
            ("empty_future", {"use_forecast": False, "n_scenarios": 1}),
            (
                "finite_demand",
                {
                    "use_forecast": True,
                    "use_finite_demand": True,
                    "finite_demand_model": finite,
                    "forecast": arrival,
                    "n_scenarios": 2,
                },
            ),
        ):
            ctrl = CommitmentSafeStochasticMpc(case.instance, case.horizon, **common, **kwargs)
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
            completed = sum(1 for st in final.values() if st == "completed")
            au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
            outcomes[label] = {"completed": completed, "au": au, "status": ctrl.last_validation_status}
        closed.append({"stem": stem, "outcomes": outcomes})

        # Offline first-epoch ranking diagnostic on public start observation.
        # Build a mid-episode observation via a short empty run's first decision state is hard;
        # use initial observation after first release by running plant once.
        from safe_time_evrp.environment.simulator import FleetSimulator

        sim = FleetSimulator(case.instance, fleet_size=case.fleet_size)
        for cid, t in case.releases[:1]:
            sim.schedule_release(cid, t)
        if sim.next_event_time() is not None:
            sim.pop_event()
        obs = sim.observation()
        diag = diagnose_epoch(case.instance, obs, case.horizon, finite, arrival, pol)
        if diag:
            diag["stem"] = stem
            audits.append(diag)

    n_disagree = sum(1 for a in audits if a.get("ranking_disagreement"))
    payload = {
        "offline_ranking_audits": audits,
        "n_ranking_disagreements": n_disagree,
        "closed_loop_empty_vs_forecast": closed,
        "mechanism_hypothesis": (
            "When rankings disagree, forecast scenarios inflate expected value of "
            "wait/charge/reject relative to serving announced customers under empty-future "
            "causal scoring; Monte Carlo variance with n_scenarios=2 amplifies flips. "
            "Restricted hindsight is offline-only."
        ),
    }
    lines = [
        "# MPC forecast decision causality",
        "",
        "## Offline ranking disagreements (same candidate set)",
        "",
        f"Disagreements: **{n_disagree}** / {len(audits)} diagnosed epochs.",
        "",
        "```json",
        json.dumps(audits, indent=2),
        "```",
        "",
        "## Closed-loop empty-future vs finite-demand",
        "",
        "```json",
        json.dumps(closed, indent=2),
        "```",
        "",
        "## Mechanism",
        "",
        payload["mechanism_hypothesis"],
        "",
        "Focused solver response: prefer empty-future causal scoring when forecast "
        "disagrees with empty-future on the incumbent first action **only if** the "
        "forecast mean advantage is below a deadband — implemented as optional "
        "`forecast_deadband` in corrected development (default off to avoid silent retuning).",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(main(), indent=2)[:4000])
