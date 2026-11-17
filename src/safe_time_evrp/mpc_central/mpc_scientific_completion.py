"""Complete remaining scientific gaps: divergence reconstruction, EV regimes,
large-instance probe, multi-budget frontier.

Development-only. Offline hindsight never enters online control.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, scalability_instance_stems, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.energy_rebuild import infinite_battery_instance
from safe_time_evrp.models.instance import NodeKind
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.mpc_decision_quality_diagnosis import (
    FOCUS,
    ProbeController,
    diagnose_state,
    first_divergence,
)
from safe_time_evrp.validation.replay import validate_log

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "research"
OUT_JSON = OUT_DIR / "MPC_SCIENTIFIC_COMPLETION.json"
OUT_MD = OUT_DIR / "MPC_SCIENTIFIC_COMPLETION.md"

# Predeclared before running (Part IV / V).
EV_REGIME_STEMS = ("r103C10", "rc108C10", "c106C15")
BUDGETS = (0.15, 0.35, 0.70, 1.50)
BUDGET_STEMS = ("r103C10", "c106C15", "rc108C5")
LARGE_STEMS = scalability_instance_stems()  # predeclared 100-customer
DYNAMICITIES = ("low", "medium", "high")


def _latency(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    ys = sorted(xs)
    n = len(ys)

    def pct(p: float) -> float:
        return ys[min(n - 1, int(p * (n - 1)))]

    return {
        "n": n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": ys[-1],
        "mean": sum(ys) / n,
        "frac_over_budget": None,
    }


def _econ(case, result) -> dict:
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    dist = executed_distance_from_log(case.instance, result.log)
    decide = [float(getattr(d, "optimize_seconds", 0.0) or 0.0) for d in result.decisions]
    return {
        "completed": completed,
        "au": au,
        "distance": dist,
        "economic": 100.0 * completed - 250.0 * au - float(dist or 0.0),
        "replay_ok": validate_log(case.instance, result.log).ok,
        "n_decisions": len(result.decisions),
        "decide_seconds": decide,
        "fallback_count": result.fallback_count,
    }


class SnapshotProbe(ProbeController):
    """Records observation snapshot fields needed for divergence reconstruction."""

    def decide(self, observation, trigger):
        d = super().decide(observation, trigger)
        self.traces[-1]["observation"] = {
            "time": observation.time,
            "accepted": list(observation.accepted),
            "released_open": list(observation.released_open),
            "completed": list(observation.completed),
            "in_service": list(getattr(observation, "in_service", ()) or ()),
            "vehicles": [
                {
                    "id": v.id,
                    "node": v.node,
                    "soc": float(v.soc),
                    "status": v.status,
                    "locked": v.locked_destination,
                }
                for v in observation.vehicles
            ],
        }
        self.traces[-1]["_obs_obj"] = observation  # in-memory only; stripped before JSON
        return d


def scale_battery(instance, factor: float):
    """Tight/generous battery: scale capacity only (arc energies unchanged)."""
    vt = instance.vehicle_type
    new_vt = replace(vt, battery_capacity=max(1e-6, vt.battery_capacity * factor))
    return replace(instance, vehicle_type=new_vt, name=f"{instance.name}_bat{factor:g}")


def sparse_chargers(instance, keep_fraction: float = 0.5):
    """Keep a predeclared subset of chargers (alphabetical), at least one."""
    chargers = sorted(nid for nid, n in instance.nodes.items() if n.kind == NodeKind.CHARGER)
    k = max(1, int(math.ceil(len(chargers) * keep_fraction))) if chargers else 0
    keep = set(chargers[:k])
    nodes = {nid: n for nid, n in instance.nodes.items() if n.kind != NodeKind.CHARGER or nid in keep}
    arcs = {(o, d): a for (o, d), a in instance.arcs.items() if o in nodes and d in nodes}
    return replace(instance, nodes=nodes, arcs=arcs, name=f"{instance.name}_sparsechg")


def slow_charge(instance, rate_factor: float = 2.0):
    """Longer charging time: scale inverse_recharge_rate up."""
    vt = instance.vehicle_type
    new_vt = replace(vt, inverse_recharge_rate=vt.inverse_recharge_rate * rate_factor)
    return replace(instance, vehicle_type=new_vt, name=f"{instance.name}_slowchg")


def _controllers(case, arrival, finite, pol, budget, *, energy_gated=True):
    inst, h = case.instance, case.horizon
    common = dict(
        alns_iterations=8,
        time_limit_seconds=budget,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=80,
    )
    css = CommitmentSafeStochasticMpc(
        inst,
        h,
        forecast=arrival,
        finite_demand_model=finite,
        n_scenarios=2,
        use_forecast=True,
        use_finite_demand=True,
        require_terminal_commitment=True,
        forecast_override_margin=50.0,
        energy_gated_charge=energy_gated,
        charge_advantage_margin=25.0,
        **common,
    )
    gn = CertificateCarryingEconomicMpc(
        inst,
        h,
        forecast=arrival,
        n_scenarios=2,
        use_forecast=False,
        scoring_mode="greedy_nominal",
        use_persistent_certificate=True,
        **common,
    )
    return css, gn


def _run_pair(case, arrival, finite, pol, budget, *, energy_gated=True):
    css_inner, gn_inner = _controllers(case, arrival, finite, pol, budget, energy_gated=energy_gated)
    css, gn = SnapshotProbe(css_inner), SnapshotProbe(gn_inner)
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
    return css, gn, css_res, gn_res, css_inner


def reconstruct_divergences(*, stems=FOCUS, n_real: int = 1, arrival=None, finite=None) -> list[dict]:
    splits = stratified_split_small()
    arrival = arrival or fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = finite or fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    rows = []
    for stem in stems:
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, _, _ = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            css, gn, css_res, gn_res, css_inner = _run_pair(case, arrival, finite, pol, 0.35)
            div = first_divergence(css.traces, gn.traces)
            cell = {
                "stem": stem,
                "realization_index": ridx,
                "css": _econ(case, css_res),
                "gn": _econ(case, gn_res),
                "delta_economic": _econ(case, css_res)["economic"] - _econ(case, gn_res)["economic"],
                "loss_events": len(getattr(css_inner.profile, "loss_events", []) or []),
                "first_divergence": None,
                "divergence_state_diag": None,
            }
            if div is None:
                rows.append(cell)
                continue
            # Strip heavy objects for JSON of divergence action records.
            css_a = {k: v for k, v in div["css"].items() if k != "_obs_obj"}
            gn_a = {k: v for k, v in div["gn"].items() if k != "_obs_obj"}
            cell["first_divergence"] = {
                "index": div["index"],
                "reason": div["reason"],
                "css": css_a,
                "gn": gn_a,
            }
            obs = div["css"].get("_obs_obj")
            if obs is not None and div["reason"] == "action_divergence":
                diag = diagnose_state(case.instance, obs, case.horizon, finite, case.releases, seed=pol)
                cell["divergence_state_diag"] = diag
                # Mechanism relative to actual chosen actions
                css_legs = tuple(div["css"]["legs"])
                gn_legs = tuple(div["gn"]["legs"])
                hs = diag.get("hindsight_winner")
                fc = diag.get("forecast_winner")
                empty = diag.get("empty_winner")
                labels = list(diag.get("mechanisms") or [])
                if hs and tuple(hs["legs"]) == gn_legs and css_legs != gn_legs:
                    labels.append("GN_matches_hindsight_CSS_does_not")
                if hs and tuple(hs["legs"]) == css_legs:
                    labels.append("CSS_matches_hindsight")
                if any(leg[2] == "charge" for leg in css_legs) and any(leg[2] == "service" for leg in gn_legs):
                    labels.append("CSS_charge_vs_GN_service")
                if tuple(div["css"].get("newly") or ()) != tuple(div["gn"].get("newly") or ()):
                    labels.append("accept_set_divergence")
                if fc and empty and fc["legs"] != empty["legs"]:
                    labels.append("forecast_empty_disagree_at_divergence")
                # Record battery / commitment state at divergence for the paper table.
                cell["divergence_plant"] = {
                    "accepted": (div["css"].get("observation") or {}).get("accepted"),
                    "soc": [v.get("soc") for v in (div["css"].get("observation") or {}).get("vehicles") or []],
                    "css_newly": div["css"].get("newly"),
                    "gn_newly": div["gn"].get("newly"),
                    "css_optimize_s": div["css"].get("optimize_seconds"),
                    "gn_optimize_s": div["gn"].get("optimize_seconds"),
                }
                cell["divergence_labels"] = labels
            rows.append(cell)
    return rows


def run_ev_regimes(*, arrival=None, finite=None) -> list[dict]:
    """Predeclared factorial: battery × charger density × dynamicity on EV_REGIME_STEMS."""
    splits = stratified_split_small()
    arrival = arrival or fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = finite or fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    regimes = [
        ("battery_tight_0.6", lambda inst: scale_battery(inst, 0.6)),
        ("battery_nominal_1.0", lambda inst: inst),
        ("battery_generous_1.5", lambda inst: scale_battery(inst, 1.5)),
        ("battery_infinite", infinite_battery_instance),
        ("chargers_sparse_0.5", lambda inst: sparse_chargers(inst, 0.5)),
        ("charge_slow_x2", lambda inst: slow_charge(inst, 2.0)),
    ]
    cells = []
    for stem in EV_REGIME_STEMS:
        for dyn in DYNAMICITIES:
            for reg_name, transform in regimes:
                env = environment_seed_for(stem, 0) & 0x7FFFFFFF
                pol = policy_seed_for(stem, 0, "shared")
                episode, _, _ = build_dynamic_episode_v2(
                    stem, environment_seed=env, policy_seed=pol, dynamicity=dyn, split="development"
                )
                case = episode.case
                try:
                    inst2 = transform(case.instance)
                    case2 = BaselineCase(
                        case_id=f"{case.case_id}|{reg_name}",
                        instance=inst2,
                        releases=case.releases,
                        fleet_size=case.fleet_size,
                        horizon=case.horizon,
                        max_replan_interval=case.max_replan_interval,
                        t_max=case.t_max,
                        tags=tuple(case.tags) + (reg_name, f"dyn={dyn}"),
                    )
                    css, gn, css_res, gn_res, css_inner = _run_pair(case2, arrival, finite, pol, 0.35)
                    css_m, gn_m = _econ(case2, css_res), _econ(case2, gn_res)
                    cells.append(
                        {
                            "stem": stem,
                            "dynamicity": dyn,
                            "regime": reg_name,
                            "css": css_m,
                            "gn": gn_m,
                            "delta_economic": css_m["economic"] - gn_m["economic"],
                            "css_charge_time_proxy": css_m.get("distance"),
                            "loss_events": len(getattr(css_inner.profile, "loss_events", []) or []),
                            "failure": None,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    cells.append(
                        {
                            "stem": stem,
                            "dynamicity": dyn,
                            "regime": reg_name,
                            "failure": f"{type(exc).__name__}:{exc}",
                            "delta_economic": None,
                        }
                    )
    return cells


def run_budget_frontier(*, arrival=None, finite=None) -> list[dict]:
    splits = stratified_split_small()
    arrival = arrival or fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = finite or fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    cells = []
    for stem in BUDGET_STEMS:
        env = environment_seed_for(stem, 0) & 0x7FFFFFFF
        pol = policy_seed_for(stem, 0, "shared")
        episode, _, _ = build_dynamic_episode_v2(
            stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
        )
        case = episode.case
        for budget in BUDGETS:
            css, gn, css_res, gn_res, css_inner = _run_pair(case, arrival, finite, pol, budget)
            css_m, gn_m = _econ(case, css_res), _econ(case, gn_res)
            lat = _latency(css_m["decide_seconds"])
            lat["frac_over_budget"] = (
                sum(1 for x in css_m["decide_seconds"] if x > budget) / max(1, len(css_m["decide_seconds"]))
            )
            cells.append(
                {
                    "stem": stem,
                    "budget": budget,
                    "css": {k: v for k, v in css_m.items() if k != "decide_seconds"},
                    "gn": {k: v for k, v in gn_m.items() if k != "decide_seconds"},
                    "delta_economic": css_m["economic"] - gn_m["economic"],
                    "css_latency": lat,
                    "css_overruns": sum(1 for x in css_m["decide_seconds"] if x > budget),
                    "loss_events": len(getattr(css_inner.profile, "loss_events", []) or []),
                    "terminal_rejects": getattr(css_inner.profile, "terminal_rejects", None),
                    "phase": {
                        "candidate_gen_sum": sum(css_inner.profile.phase_candidate_gen or []),
                        "scoring_sum": sum(css_inner.profile.phase_scoring or []),
                        "terminal_sum": sum(css_inner.profile.phase_terminal or []),
                    },
                }
            )
    return cells


def run_large_instance_probe(*, arrival=None, finite=None) -> list[dict]:
    """Credibility probe on predeclared 100-customer stems (1 realization, medium)."""
    splits = stratified_split_small()
    arrival = arrival or fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = finite or fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    cells = []
    for stem in LARGE_STEMS:
        env = environment_seed_for(stem, 0) & 0x7FFFFFFF
        pol = policy_seed_for(stem, 0, "shared")
        try:
            episode, _, _ = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            # Credibility probe: 0.70s cooperative budget; plant unchanged.
            # Fewer ALNS iterations only inside controllers via shared helper override.
            t0 = perf_counter()

            def _pair_large():
                inst, h = case.instance, case.horizon
                common = dict(
                    alns_iterations=4,
                    time_limit_seconds=0.70,
                    seed=pol,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=40,
                )
                css_inner = CommitmentSafeStochasticMpc(
                    inst,
                    h,
                    forecast=arrival,
                    finite_demand_model=finite,
                    n_scenarios=1,
                    use_forecast=True,
                    use_finite_demand=True,
                    require_terminal_commitment=True,
                    forecast_override_margin=50.0,
                    energy_gated_charge=True,
                    **common,
                )
                gn_inner = CertificateCarryingEconomicMpc(
                    inst,
                    h,
                    forecast=arrival,
                    n_scenarios=1,
                    use_forecast=False,
                    scoring_mode="greedy_nominal",
                    use_persistent_certificate=True,
                    **common,
                )
                css, gn = SnapshotProbe(css_inner), SnapshotProbe(gn_inner)
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
                return css, gn, css_res, gn_res, css_inner

            css, gn, css_res, gn_res, css_inner = _pair_large()
            wall = perf_counter() - t0
            css_m, gn_m = _econ(case, css_res), _econ(case, gn_res)
            lat = _latency(css_m["decide_seconds"])
            lat["frac_over_budget"] = sum(1 for x in css_m["decide_seconds"] if x > 0.70) / max(
                1, len(css_m["decide_seconds"])
            )
            cells.append(
                {
                    "stem": stem,
                    "n_customers": len(case.instance.customer_ids()),
                    "fleet_size": case.fleet_size,
                    "wall_seconds": wall,
                    "css": {k: v for k, v in css_m.items() if k != "decide_seconds"},
                    "gn": {k: v for k, v in gn_m.items() if k != "decide_seconds"},
                    "delta_economic": css_m["economic"] - gn_m["economic"],
                    "css_latency": lat,
                    "loss_events": len(getattr(css_inner.profile, "loss_events", []) or []),
                    "failure": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            cells.append({"stem": stem, "failure": f"{type(exc).__name__}:{exc}"})
    return cells


def _write_md(payload: dict) -> None:
    lines = [
        "# Scientific completion — remaining gaps",
        "",
        "Protocol: development-only; failures included; objective unchanged.",
        "",
        "## 1. First-divergence reconstruction",
        "",
        "| Stem | Δ econ | Div t | CSS action | GN action | Labels |",
        "|---|---:|---:|---|---|---|",
    ]
    for c in payload["divergences"]:
        div = c.get("first_divergence") or {}
        css_a = div.get("css") or {}
        gn_a = div.get("gn") or {}
        lines.append(
            "| {stem} | {de:.1f} | {t} | {ca} | {ga} | {lab} |".format(
                stem=c["stem"],
                de=c["delta_economic"],
                t=f"{css_a.get('time', float('nan')):.2f}" if css_a else "—",
                ca=f"{css_a.get('legs')}/{css_a.get('newly')}",
                ga=f"{gn_a.get('legs')}/{gn_a.get('newly')}",
                lab=",".join(c.get("divergence_labels") or []) or "—",
            )
        )
    lines.extend(
        [
            "",
            "## 2. EV regime factorial (all cells)",
            "",
            "| Stem | Dyn | Regime | Δ econ CSS−GN | CSS comp | GN comp | Failure |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for c in payload["ev_regimes"]:
        lines.append(
            "| {stem} | {dyn} | {reg} | {de} | {cc} | {gc} | {fail} |".format(
                stem=c["stem"],
                dyn=c["dynamicity"],
                reg=c["regime"],
                de="—" if c.get("delta_economic") is None else f"{c['delta_economic']:.1f}",
                cc="—" if not c.get("css") else c["css"]["completed"],
                gc="—" if not c.get("gn") else c["gn"]["completed"],
                fail=c.get("failure") or "",
            )
        )
    lines.extend(
        [
            "",
            "## 3. Computation–performance frontier",
            "",
            "| Stem | Budget | Δ econ | CSS p50 | CSS p99 | Overruns | Loss |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for c in payload["budget_frontier"]:
        lat = c["css_latency"]
        lines.append(
            "| {stem} | {b:.2f} | {de:.1f} | {p50:.3f} | {p99:.3f} | {ov} | {loss} |".format(
                stem=c["stem"],
                b=c["budget"],
                de=c["delta_economic"],
                p50=lat.get("p50") or 0,
                p99=lat.get("p99") or 0,
                ov=c["css_overruns"],
                loss=c["loss_events"],
            )
        )
    lines.extend(
        [
            "",
            "## 4. Large-instance probe (100 customers)",
            "",
            "```json",
            json.dumps(payload["large_instances"], indent=2)[:8000],
            "```",
            "",
            "## Reading",
            "",
            payload.get("reading", ""),
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_all() -> dict:
    splits = stratified_split_small()
    arrival = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
    divergences = reconstruct_divergences(arrival=arrival, finite=finite)
    ev_regimes = run_ev_regimes(arrival=arrival, finite=finite)
    budget_frontier = run_budget_frontier(arrival=arrival, finite=finite)
    large_instances = run_large_instance_probe(arrival=arrival, finite=finite)

    # Strip in-memory observation objects if any leaked
    for c in divergences:
        div = c.get("first_divergence")
        if div:
            for side in ("css", "gn"):
                if div.get(side) and "_obs_obj" in div[side]:
                    del div[side]["_obs_obj"]

    n_reg = len(ev_regimes)
    n_fail = sum(1 for c in ev_regimes if c.get("failure"))
    n_css_better = sum(1 for c in ev_regimes if (c.get("delta_economic") or 0) > 0)
    n_css_worse = sum(1 for c in ev_regimes if c.get("delta_economic") is not None and c["delta_economic"] < 0)
    reading = (
        f"EV regimes: {n_reg} cells, {n_fail} failures, CSS better {n_css_better} / worse {n_css_worse}. "
        "Divergence labels document charge-vs-service and hindsight agreement. "
        "Budget frontier reports cooperative overruns without redefining the objective. "
        "Large stems are a credibility probe, not a confirmatory claim."
    )
    payload = {
        "protocol": "scientific_completion_v1",
        "predeclared": {
            "ev_regime_stems": list(EV_REGIME_STEMS),
            "budgets": list(BUDGETS),
            "budget_stems": list(BUDGET_STEMS),
            "large_stems": list(LARGE_STEMS),
            "dynamicities": list(DYNAMICITIES),
        },
        "divergences": divergences,
        "ev_regimes": ev_regimes,
        "budget_frontier": budget_frontier,
        "large_instances": large_instances,
        "reading": reading,
        "ev_regime_tally": {"n": n_reg, "failures": n_fail, "css_better": n_css_better, "css_worse": n_css_worse},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_md(payload)
    return payload


if __name__ == "__main__":
    p = run_all()
    print(
        json.dumps(
            {
                "n_divergences": len(p["divergences"]),
                "ev_regime_tally": p["ev_regime_tally"],
                "n_budget_cells": len(p["budget_frontier"]),
                "n_large": len(p["large_instances"]),
            },
            indent=2,
        )
    )
