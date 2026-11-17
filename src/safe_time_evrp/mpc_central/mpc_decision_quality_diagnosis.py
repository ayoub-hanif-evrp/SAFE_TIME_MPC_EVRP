"""Matched decision-state diagnosis: forecast vs ranking vs action-space vs computation.

Offline hindsight uses realized futures for analysis only — never online.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model, sample_finite_demand_scenarios
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey, generate_counterfactual_actions
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value
from safe_time_evrp.validation.replay import validate_log

ROOT = Path(__file__).resolve().parents[3]
OUT_MD = ROOT / "docs" / "research" / "MPC_DECISION_QUALITY_DIAGNOSIS.md"
OUT_JSON = ROOT / "docs" / "research" / "MPC_DECISION_QUALITY_DIAGNOSIS.json"

# Worst economic losses vs GN (corrected campaign) + one win for contrast.
FOCUS = ("r103C10", "rc108C10", "rc108C15", "c106C15")


@dataclass
class MechanismCounts:
    prediction_error: int = 0
    ranking_error: int = 0
    action_space_error: int = 0
    horizon_error: int = 0
    computation_error: int = 0
    feasibility_error: int = 0


def _econ(result) -> float:
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    dist = executed_distance_from_log(result.instance if hasattr(result, "instance") else None, result.log)
    # distance helper needs instance — caller passes via log only; recompute outside if needed
    return 100.0 * completed - 250.0 * au - float(dist or 0.0)


def _econ_from(case, result) -> dict:
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    dist = executed_distance_from_log(case.instance, result.log)
    return {
        "completed": completed,
        "au": au,
        "distance": dist,
        "economic": 100.0 * completed - 250.0 * au - float(dist or 0.0),
        "replay_ok": validate_log(case.instance, result.log).ok,
    }


def _realize_future_forecast(instance, releases, now: float, horizon: float):
    """Offline-only: convert realized releases in (now, now+H] into ForecastCustomer list."""
    from safe_time_evrp.mpc3c.forecast import ForecastCustomer

    out = []
    for item in releases:
        if isinstance(item, tuple) and len(item) >= 2:
            cid, t = str(item[0]), float(item[1])
        else:
            cid = str(getattr(item, "customer_id", ""))
            t = float(getattr(item, "time", getattr(item, "release_time", -1)))
        if t <= now or t > now + horizon or not cid:
            continue
        node = instance.nodes.get(cid)
        out.append(
            ForecastCustomer(
                customer_id=cid,
                ready_time=float(node.window.ready if node else t),
                due_time=float(node.window.due if node else t + 100.0),
                x=float(node.x if node else 0.0),
                y=float(node.y if node else 0.0),
                demand=float(node.demand if node else 1.0),
                service_time=float(node.service_time if node else 1.0),
                announcement_time=t,
                source="realized_hindsight_offline",
            )
        )
    return out


def diagnose_state(
    inst,
    obs: Observation,
    horizon: float,
    finite,
    releases,
    *,
    seed: int,
    budget: float = 0.35,
) -> dict:
    public = make_public_snapshot(inst, obs, horizon).instance
    t0 = perf_counter()
    cands, _ = generate_counterfactual_actions(
        inst,
        obs,
        horizon=horizon,
        alns_iterations=8,
        alns_time=min(0.12, budget * 0.3),
        seed=seed,
        include_solver_baselines=True,
        include_b1=True,
    )
    gen_s = perf_counter() - t0
    feasible = []
    stage0_fail = 0
    for name, cand in cands:
        rep = validate_continuation(public, obs, cand.routes, require_new=frozenset(cand.newly_accepted))
        if rep.ok:
            feasible.append((name, cand, list(rep.served)))
        else:
            stage0_fail += 1

    empty = [[]]
    forecast_sc = sample_finite_demand_scenarios(finite, obs, inst, horizon=horizon, n_scenarios=2, seed=seed)
    hindsight = [_realize_future_forecast(inst, releases, obs.time, horizon)]

    rows = []
    for name, cand, _served in feasible:
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
        key = FirstActionKey.from_decision(d)
        ve, se = expected_rollout_value(
            inst, obs, d, empty, horizon=horizon, max_scenarios=1, scoring_mode="causal", max_events=60
        )
        vf, sf = expected_rollout_value(
            inst, obs, d, forecast_sc, horizon=horizon, max_scenarios=2, scoring_mode="causal", max_events=60
        )
        vh, sh = expected_rollout_value(
            inst, obs, d, hindsight, horizon=horizon, max_scenarios=1, scoring_mode="causal", max_events=60
        )
        rows.append(
            {
                "name": name,
                "legs": key.first_legs,
                "newly": list(d.newly_accepted),
                "empty_v": ve,
                "forecast_v": vf,
                "hindsight_v": vh,
                "empty_ok": all(s.replay_ok for s in se),
                "forecast_ok": all(s.replay_ok for s in sf),
                "hindsight_ok": all(s.replay_ok for s in sh),
            }
        )

    def winner(key):
        ok = [r for r in rows if r[key.replace("_v", "_ok")] and r[key] > -1e8]
        if not ok:
            return None
        return max(ok, key=lambda r: r[key])

    w_empty = winner("empty_v")
    w_fc = winner("forecast_v")
    w_hs = winner("hindsight_v")

    # Mechanism labels for this state.
    mechanisms = []
    if w_hs is None:
        mechanisms.append("F_feasibility_or_empty_set")
    else:
        headroom = None
        if w_empty is not None:
            headroom = w_hs["hindsight_v"] - w_empty["empty_v"]
        if w_fc is not None and w_hs is not None and w_fc["legs"] != w_hs["legs"]:
            # Forecast ranking differs from hindsight → ranking or prediction
            if w_empty is not None and w_empty["legs"] == w_hs["legs"]:
                mechanisms.append("B_ranking_error")  # empty got it right; forecast wrong
            else:
                mechanisms.append("A_or_B_prediction_or_ranking")
        if w_empty is not None and w_hs is not None and w_empty["legs"] != w_hs["legs"]:
            if w_fc is not None and w_fc["legs"] == w_hs["legs"]:
                mechanisms.append("A_prediction_useful_but_empty_missed")
            else:
                # Best hindsight action may be missing from set
                mechanisms.append("B_or_C_ranking_or_action_space")
        if headroom is not None and abs(headroom) < 1.0 and w_empty and w_hs and w_empty["legs"] == w_hs["legs"]:
            mechanisms.append("little_headroom_in_candidate_set")
        if gen_s > 0.25 * budget:
            mechanisms.append("E_computation_pressure_candidate_gen")

    # Action-space: is any feasible action substantially better under hindsight than empty winner?
    action_space_gap = 0.0
    if w_hs and w_empty and w_hs["hindsight_v"] > -1e8 and w_empty["empty_v"] > -1e8:
        action_space_gap = w_hs["hindsight_v"] - w_empty["hindsight_v"]

    return {
        "time": obs.time,
        "accepted": list(obs.accepted),
        "soc": [float(v.soc) for v in obs.vehicles],
        "n_raw_candidates": len(cands),
        "n_feasible": len(feasible),
        "stage0_fail": stage0_fail,
        "candidate_gen_seconds": gen_s,
        "empty_winner": w_empty,
        "forecast_winner": w_fc,
        "hindsight_winner": w_hs,
        "ranking_disagree_empty_forecast": (
            w_empty is not None and w_fc is not None and w_empty["legs"] != w_fc["legs"]
        ),
        "ranking_disagree_forecast_hindsight": (w_fc is not None and w_hs is not None and w_fc["legs"] != w_hs["legs"]),
        "action_space_hindsight_gap_vs_empty": action_space_gap,
        "mechanisms": mechanisms,
        "top3_hindsight": sorted(
            [r for r in rows if r["hindsight_ok"] and r["hindsight_v"] > -1e8],
            key=lambda r: r["hindsight_v"],
            reverse=True,
        )[:3],
        "top3_forecast": sorted(
            [r for r in rows if r["forecast_ok"] and r["forecast_v"] > -1e8],
            key=lambda r: r["forecast_v"],
            reverse=True,
        )[:3],
    }


class ProbeController:
    """Wraps a base controller and records first-action keys per decide."""

    def __init__(self, inner):
        self.inner = inner
        self.traces: list[dict] = []

    def decide(self, observation, trigger):
        d = self.inner.decide(observation, trigger)
        key = FirstActionKey.from_decision(d)
        self.traces.append(
            {
                "time": observation.time,
                "trigger": trigger,
                "legs": key.first_legs,
                "newly": list(d.newly_accepted),
                "rejected": list(d.rejected),
                "fallback": d.fallback_used,
                "status": getattr(self.inner, "last_validation_status", None),
                "optimize_seconds": d.optimize_seconds,
                "notes": list(d.notes)[:40],
            }
        )
        return d

    def __getattr__(self, name):
        return getattr(self.inner, name)


def first_divergence(css_traces, gn_traces) -> dict | None:
    n = min(len(css_traces), len(gn_traces))
    for i in range(n):
        a, b = css_traces[i], gn_traces[i]
        if abs(a["time"] - b["time"]) > 1e-6:
            return {"index": i, "reason": "time_mismatch", "css": a, "gn": b}
        if a["legs"] != b["legs"] or tuple(a["newly"]) != tuple(b["newly"]):
            return {"index": i, "reason": "action_divergence", "css": a, "gn": b}
    return None


def _leg_kinds(legs) -> set[str]:
    return {str(leg[2]) for leg in (legs or [])}


def classify_serve_vs_passive(div: dict | None) -> str | None:
    """Label trivial losses: GN serves/accepts while CSS idles/charges/rejects."""
    if not div or div.get("reason") != "action_divergence":
        return None
    css, gn = div["css"], div["gn"]
    css_kinds, gn_kinds = _leg_kinds(css.get("legs")), _leg_kinds(gn.get("legs"))
    gn_serves = bool(gn.get("newly")) or ("service" in gn_kinds) or ("travel" in gn_kinds)
    css_passive = (not css.get("newly")) and css_kinds.issubset({"idle", "wait", "charge", ""})
    css_rejects = bool(css.get("rejected")) and not css.get("newly")
    if gn_serves and css_passive:
        return "css_passive_vs_gn_serve"
    if gn_serves and css_rejects:
        return "css_reject_vs_gn_serve"
    return "other_action_divergence"


def run_diagnosis(*, stems=FOCUS, n_real: int = 1) -> dict:
    splits = stratified_split_small()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    cells = []
    counts = MechanismCounts()

    for stem in stems:
        assert stem in splits["development"] or stem in splits["train"] or stem in splits["test"]
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, _, _ = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            common = dict(
                alns_iterations=8,
                time_limit_seconds=0.35,
                seed=pol,
                max_replan_interval=case.max_replan_interval,
                rollout_max_events=80,
            )
            css_inner = CommitmentSafeStochasticMpc(
                case.instance,
                case.horizon,
                forecast=arrival,
                finite_demand_model=finite,
                n_scenarios=2,
                # Proposed SPI-empty + GN-scored base (forecast demoted on development evidence).
                use_forecast=False,
                use_finite_demand=False,
                require_terminal_commitment=True,
                spi_mode=True,
                spi_advantage_margin=0.0,
                **common,
            )
            gn_inner = CertificateCarryingEconomicMpc(
                case.instance,
                case.horizon,
                forecast=arrival,
                n_scenarios=2,
                use_forecast=False,
                scoring_mode="greedy_nominal",
                use_persistent_certificate=True,
                **common,
            )
            css = ProbeController(css_inner)
            gn = ProbeController(gn_inner)
            css_res = run_episode(
                case.instance,
                case.releases,
                fleet_size=case.fleet_size,
                horizon=case.horizon,
                max_replan_interval=case.max_replan_interval,
                t_max=case.t_max,
                controller=css,
            )
            gn_res = run_episode(
                case.instance,
                case.releases,
                fleet_size=case.fleet_size,
                horizon=case.horizon,
                max_replan_interval=case.max_replan_interval,
                t_max=case.t_max,
                controller=gn,
            )
            css_m = _econ_from(case, css_res)
            gn_m = _econ_from(case, gn_res)
            div = first_divergence(css.traces, gn.traces)
            serve_label = classify_serve_vs_passive(div)
            from safe_time_evrp.environment.energy import NominalLinearEnergy
            from safe_time_evrp.environment.simulator import FleetSimulator

            sim0 = FleetSimulator(case.instance, case.fleet_size, NominalLinearEnergy())
            for cid, t in case.releases:
                sim0.schedule_release(cid, t)
            obs0 = sim0.observation()
            state_diag = diagnose_state(case.instance, obs0, case.horizon, finite, case.releases, seed=pol)
            for m in state_diag.get("mechanisms") or []:
                if m.startswith("A"):
                    counts.prediction_error += 1
                if "B_ranking" in m or m.startswith("B"):
                    counts.ranking_error += 1
                if "C" in m or "action_space" in m:
                    counts.action_space_error += 1
                if "E_computation" in m:
                    counts.computation_error += 1
                if "F_" in m:
                    counts.feasibility_error += 1

            cells.append(
                {
                    "stem": stem,
                    "realization_index": ridx,
                    "environment_seed": env,
                    "css": css_m,
                    "gn": gn_m,
                    "delta_economic": css_m["economic"] - gn_m["economic"],
                    "first_divergence": div,
                    "serve_vs_passive_label": serve_label,
                    "spi_keeps": int(getattr(getattr(css_inner, "profile", None), "spi_keeps", 0) or 0),
                    "spi_overrides": int(getattr(getattr(css_inner, "profile", None), "spi_overrides", 0) or 0),
                    "state_diag_t0": state_diag,
                    "css_n_decisions": len(css.traces),
                    "gn_n_decisions": len(gn.traces),
                    "css_over_budget": sum(1 for t in css.traces if t["optimize_seconds"] > 0.35),
                    "css_loss_events": len(getattr(getattr(css_inner, "profile", None), "loss_events", []) or []),
                }
            )

    trivial_losses = sum(
        1 for c in cells if c.get("serve_vs_passive_label") in ("css_passive_vs_gn_serve", "css_reject_vs_gn_serve")
    )
    payload = {
        "protocol": "decision_quality_diagnosis_spi_v1",
        "selection_law": "spi_crn",
        "stems": list(stems),
        "mechanism_counts": asdict(counts),
        "trivial_css_passive_vs_gn_serve_count": trivial_losses,
        "n_cells": len(cells),
        "cells": cells,
        "interpretation_keys": {
            "A": "prediction_error",
            "B": "ranking_error",
            "C": "action_space_error",
            "D": "horizon_error",
            "E": "computation_error",
            "F": "feasibility_error",
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_md(payload)
    return payload


def _write_md(payload: dict) -> None:
    lines = [
        "# MPC decision-quality diagnosis",
        "",
        "Offline hindsight is diagnostic only.",
        "",
        "## Mechanism tallies (t=0 matched candidate sets)",
        "",
        "```json",
        json.dumps(payload["mechanism_counts"], indent=2),
        "```",
        "",
        "## Per-stem closed-loop vs first divergence",
        "",
        f"- Selection law: `{payload.get('selection_law')}`",
        f"- Trivial CSS passive/reject vs GN serve at first divergence: "
        f"**{payload.get('trivial_css_passive_vs_gn_serve_count', 0)}** / {payload.get('n_cells', len(payload['cells']))}",
        "",
        "| Stem | Δ econ | First div | Serve-loss | SPI keep/ov | Empty≠FC | Mechanisms |",
        "|---|---:|---|---|---|---|---|",
    ]
    for c in payload["cells"]:
        sd = c.get("state_diag_t0") or {}
        div = c.get("first_divergence")
        div_s = "none" if div is None else f"t={div['css']['time']:.2f}"
        lines.append(
            "| {stem} | {de:.1f} | {div} | {sl} | {sk}/{so} | {ed} | {mech} |".format(
                stem=c["stem"],
                de=c["delta_economic"],
                div=div_s,
                sl=c.get("serve_vs_passive_label") or "—",
                sk=c.get("spi_keeps", 0),
                so=c.get("spi_overrides", 0),
                ed=sd.get("ranking_disagree_empty_forecast"),
                mech=",".join(sd.get("mechanisms") or []) or "—",
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- Large hindsight gap with empty≈forecast winners ⇒ **C action-space** or missing charge/route.",
            "- Forecast≠hindsight while empty=hindsight ⇒ **B ranking** (forecast harms).",
            "- Forecast=hindsight≠empty ⇒ prediction useful if used.",
            "- Stage-0 / replay fails on promising actions ⇒ **F feasibility** mismatch.",
            "- High candidate-gen time ⇒ **E computation**.",
            "",
            "```json",
            json.dumps(
                [
                    {
                        "stem": c["stem"],
                        "delta": c["delta_economic"],
                        "div": c.get("first_divergence"),
                        "diag": c.get("state_diag_t0"),
                    }
                    for c in payload["cells"]
                ],
                indent=2,
            )[:12000],
            "```",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    p = run_diagnosis()
    print(json.dumps({"mechanism_counts": p["mechanism_counts"], "n_cells": len(p["cells"])}, indent=2))
