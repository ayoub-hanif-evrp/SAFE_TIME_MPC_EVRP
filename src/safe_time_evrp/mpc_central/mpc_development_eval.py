"""Development comparison: Commitment-Safe Stochastic MPC vs B1/M1/GN/stochastic CC-E.

Development stems only. Does not use inspected final-test cells for tuning.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.models.energy_rebuild import infinite_battery_instance
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.forecast_stall_diagnostic import DIAGNOSTIC_STEMS
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 10
BUDGET = 0.35
N_SCEN = 2
N_REAL = 2
ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_DEVELOPMENT_COMPARISON.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_DEVELOPMENT_COMPARISON.md"
OUT_TERM = ROOT / "docs" / "experiments" / "MPC_TERMINAL_FEASIBILITY_VALIDATION.md"


def _latency(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    ys = sorted(xs)
    n = len(ys)

    def pct(p: float) -> float:
        return ys[min(n - 1, int(p * (n - 1)))]

    return {
        "n": n,
        "mean": sum(ys) / n,
        "median": statistics.median(ys),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": ys[-1],
        "frac_over_budget": sum(1 for x in ys if x > BUDGET) / n,
    }


def _summarize(case, name, result, ctrl, wall, failure=None):
    if failure:
        return {"controller": name, "failure": failure, "completed_count": None, "wall_seconds": wall}
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    rejected = sum(1 for st in final.values() if st == "rejected")
    dist = executed_distance_from_log(case.instance, result.log)
    decide_secs = list(getattr(getattr(ctrl, "profile", None), "decide_seconds", []) or [])
    overruns = getattr(getattr(ctrl, "profile", None), "deadline_overruns", None)
    term_rej = getattr(getattr(ctrl, "profile", None), "terminal_rejects", None)
    econ = 100.0 * completed - 250.0 * au - 1.0 * (dist or 0.0)
    return {
        "controller": name,
        "failure": None if rep.ok else f"replay:{rep.code}",
        "replay_ok": rep.ok,
        "completed_count": completed,
        "accepted_unfulfilled_count": au,
        "rejected_count": rejected,
        "executed_distance": dist,
        "economic_objective": econ,
        "optimize_seconds": result.optimize_seconds,
        "wall_seconds": wall,
        "termination_reason": result.termination_reason,
        "deadline_overruns": overruns,
        "terminal_rejects": term_rej,
        "n_decisions": len(result.decisions),
        "fallback_count": result.fallback_count,
        "decide_latency": _latency(decide_secs),
        "certificate_status_last": getattr(ctrl, "last_validation_status", None),
    }


def _run(case, ctrl, name):
    t0 = time.perf_counter()
    try:
        result = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
        )
        return _summarize(case, name, result, ctrl, time.perf_counter() - t0)
    except Exception as exc:  # noqa: BLE001
        return _summarize(case, name, None, ctrl, time.perf_counter() - t0, failure=f"{type(exc).__name__}:{exc}")


def _controllers(case, *, arrival, finite, pol, budget, infinite_battery=False):
    inst = infinite_battery_instance(case.instance) if infinite_battery else case.instance
    common = dict(
        alns_iterations=ALNS_ITER,
        time_limit_seconds=budget,
        seed=pol,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=100,
    )
    return {
        "b1": FullValidationAlnsMpc(inst, case.horizon, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol),
        "m1": CertificateCarryingAlnsMpc(inst, case.horizon, iterations=ALNS_ITER, time_limit_seconds=budget, seed=pol),
        "cce_greedy_nominal": CertificateCarryingEconomicMpc(
            inst,
            case.horizon,
            forecast=arrival,
            n_scenarios=N_SCEN,
            use_forecast=False,
            scoring_mode="greedy_nominal",
            use_persistent_certificate=True,
            **common,
        ),
        "stochastic_cce_causal": CertificateCarryingEconomicMpc(
            inst,
            case.horizon,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            scoring_mode="causal",
            use_persistent_certificate=True,
            **common,
        ),
        "commitment_safe_stochastic_mpc": CommitmentSafeStochasticMpc(
            inst,
            case.horizon,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=True,
            **common,
        ),
        # Ablations (proposed method variants)
        "css_mpc_no_forecast": CommitmentSafeStochasticMpc(
            inst,
            case.horizon,
            forecast=arrival,
            n_scenarios=1,
            use_forecast=False,
            require_terminal_commitment=True,
            **common,
        ),
        "css_mpc_no_terminal": CommitmentSafeStochasticMpc(
            inst,
            case.horizon,
            forecast=arrival,
            finite_demand_model=finite,
            n_scenarios=N_SCEN,
            use_forecast=True,
            use_finite_demand=True,
            require_terminal_commitment=False,
            **common,
        ),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None}
    m = sum(xs) / len(xs)
    if len(xs) == 1:
        return {"n": 1, "mean": m, "std": 0.0}
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return {"n": len(xs), "mean": m, "std": var**0.5}


def _paired(rows, a, b, key="completed_count"):
    deltas, wins = [], {"better": 0, "worse": 0, "tie": 0}
    for row in rows:
        ca, cb = row["controllers"].get(a), row["controllers"].get(b)
        if not ca or not cb or ca.get(key) is None or cb.get(key) is None:
            continue
        if ca.get("replay_ok") is False or cb.get("replay_ok") is False:
            continue
        d = ca[key] - cb[key]
        deltas.append(d)
        wins["better" if d > 0 else "worse" if d < 0 else "tie"] += 1
    return {"delta": _mean(deltas), "tally": wins, "metric": key}


def development_stems():
    splits = stratified_split_small()
    # Prefer diagnostic development stems; exclude known inspected final set.
    inspected = {"c208C15", "c103C5", "c101C10", "r201C5", "r202C10", "rc201C5"}
    train_set = set(splits["train"])
    test_set = set(splits["test"])
    stems = [s for s in DIAGNOSTIC_STEMS if s not in test_set and s not in inspected]
    if len(stems) < 6:
        stems = [s for s in DIAGNOSTIC_STEMS if s not in inspected][:9]
    split_map = {s: ("train" if s in train_set else "development") for s in stems}
    return stems[:9], split_map, splits


def run_development(*, n_real: int = N_REAL, budget: float = BUDGET, include_infbat: bool = True):
    stems, split_map, splits = development_stems()
    from safe_time_evrp.data.dynamic_schneider import load_instance

    train_inst = [load_instance(s) for s in splits["train"]]
    arrival = fit_empirical_arrivals(train_inst)
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)

    rows = []
    for stem in stems:
        for ridx in range(n_real):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, classifications, fleet = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            cell = {
                "stem": stem,
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "infinite_battery": False,
                "n_late": sum(1 for c in classifications if c.late_for_depot_admit),
                "fleet_meta": fleet,
                "controllers": {},
            }
            for name, ctrl in _controllers(
                case, arrival=arrival, finite=finite, pol=pol, budget=budget, infinite_battery=False
            ).items():
                cell["controllers"][name] = _run(case, ctrl, name)
            rows.append(cell)

    inf_rows = []
    if include_infbat:
        for stem in stems[:3]:
            for ridx in range(1):
                env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
                pol = policy_seed_for(stem, ridx, "shared")
                episode, classifications, fleet = build_dynamic_episode_v2(
                    stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
                )
                case = episode.case
                from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase

                case_inf = BaselineCase(
                    case_id=case.case_id + "_infbat",
                    instance=infinite_battery_instance(case.instance),
                    releases=case.releases,
                    fleet_size=case.fleet_size,
                    horizon=case.horizon,
                    max_replan_interval=case.max_replan_interval,
                    t_max=case.t_max,
                    tags=tuple(case.tags) + ("infinite_battery",),
                )
                cell = {
                    "stem": stem,
                    "realization_index": ridx,
                    "environment_seed": env,
                    "policy_seed": pol,
                    "infinite_battery": True,
                    "controllers": {},
                }
                # Only compare proposed vs GN under consistent rebuild.
                ctrls = _controllers(
                    case_inf, arrival=arrival, finite=finite, pol=pol, budget=budget, infinite_battery=False
                )
                for name in ("cce_greedy_nominal", "commitment_safe_stochastic_mpc"):
                    cell["controllers"][name] = _run(case_inf, ctrls[name], name)
                inf_rows.append(cell)

    def aggregate(rs, names):
        out = {}
        for name in names:
            comps, econs, replay_fail = [], [], 0
            overruns = 0
            lat_all = []
            for row in rs:
                c = row["controllers"].get(name)
                if not c:
                    continue
                if c.get("replay_ok") is False or c.get("failure"):
                    replay_fail += 1
                    continue
                comps.append(c.get("completed_count"))
                econs.append(c.get("economic_objective"))
                overruns += int(c.get("deadline_overruns") or 0)
                lat = c.get("decide_latency") or {}
                # per-episode latency stats already aggregated; keep means
                if lat.get("mean") is not None:
                    lat_all.append(lat["mean"])
            out[name] = {
                "completed": _mean(comps),
                "economic": _mean(econs),
                "replay_failures": replay_fail,
                "deadline_overruns_sum": overruns,
                "mean_decide_latency_across_episodes": _mean(lat_all),
            }
        return out

    names = [
        "b1",
        "m1",
        "cce_greedy_nominal",
        "stochastic_cce_causal",
        "commitment_safe_stochastic_mpc",
        "css_mpc_no_forecast",
        "css_mpc_no_terminal",
    ]
    summary = aggregate(rows, names)
    paired = {
        "css_vs_gn_completed": _paired(rows, "commitment_safe_stochastic_mpc", "cce_greedy_nominal"),
        "css_vs_gn_economic": _paired(
            rows, "commitment_safe_stochastic_mpc", "cce_greedy_nominal", key="economic_objective"
        ),
        "css_vs_stochastic_cce": _paired(rows, "commitment_safe_stochastic_mpc", "stochastic_cce_causal"),
        "css_vs_m1": _paired(rows, "commitment_safe_stochastic_mpc", "m1"),
        "css_vs_b1": _paired(rows, "commitment_safe_stochastic_mpc", "b1"),
        "css_vs_no_forecast": _paired(rows, "commitment_safe_stochastic_mpc", "css_mpc_no_forecast"),
        "css_vs_no_terminal": _paired(rows, "commitment_safe_stochastic_mpc", "css_mpc_no_terminal"),
    }

    gn = summary["cce_greedy_nominal"]["completed"].get("mean")
    css = summary["commitment_safe_stochastic_mpc"]["completed"].get("mean")
    gn_e = summary["cce_greedy_nominal"]["economic"].get("mean")
    css_e = summary["commitment_safe_stochastic_mpc"]["economic"].get("mean")
    econ_pair = paired["css_vs_gn_economic"]
    comp_pair = paired["css_vs_gn_completed"]
    gate = {"pass": False, "reason": ""}
    # Honest gate: must not lose substantially to greedy-nominal on completed,
    # and must show positive mean paired economic OR completed advantage with better>worse.
    if css is not None and gn is not None and css_e is not None and gn_e is not None:
        comp_t = comp_pair["tally"]
        econ_t = econ_pair["tally"]
        mean_comp = comp_pair["delta"].get("mean")
        mean_econ = econ_pair["delta"].get("mean")
        loses_substantially = mean_comp is not None and mean_comp <= -0.5
        wins_completed = (
            mean_comp is not None and mean_comp >= 0.25 and comp_t["better"] > comp_t["worse"]
        )
        wins_economic = (
            mean_econ is not None and mean_econ >= 25.0 and econ_t["better"] > econ_t["worse"]
        )
        if loses_substantially:
            gate["reason"] = (
                f"CSS-MPC loses substantially to greedy-nominal on completed "
                f"(mean_delta={mean_comp}, tally={comp_t}; means css={css}, gn={gn}). "
                f"Economic mean_delta={mean_econ}, tally={econ_t}."
            )
        elif wins_completed or wins_economic:
            gate["pass"] = True
            gate["reason"] = (
                "CSS-MPC clears development advantage vs greedy-nominal "
                f"(completed_delta={mean_comp}, economic_delta={mean_econ})."
            )
        else:
            gate["reason"] = (
                f"CSS-MPC does not show a credible paired advantage vs greedy-nominal "
                f"(completed_delta={mean_comp}, tally={comp_t}; "
                f"economic_delta={mean_econ}, tally={econ_t})."
            )
    else:
        gate["reason"] = "Missing aggregate means."

    inf_summary = aggregate(inf_rows, ["cce_greedy_nominal", "commitment_safe_stochastic_mpc"]) if inf_rows else {}

    payload = {
        "protocol": "mpc_development_v1",
        "budget_seconds": budget,
        "n_scenarios": N_SCEN,
        "stems": stems,
        "n_realizations": n_real,
        "summary": summary,
        "paired": paired,
        "development_gate": gate,
        "infinite_battery_summary": inf_summary,
        "infinite_battery_rows": inf_rows,
        "rows": rows,
        "approximation_class": "restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_md(payload)
    _write_terminal_doc()
    return payload


def _write_md(payload: dict) -> None:
    g = payload["development_gate"]
    lines = [
        "# MPC development comparison",
        "",
        f"**Gate:** `{'PASS' if g['pass'] else 'FAIL'}` — {g['reason']}",
        "",
        f"Approximation class: `{payload['approximation_class']}`",
        "",
        f"Budget: {payload['budget_seconds']}s cooperative wall; scenarios={payload['n_scenarios']}.",
        "",
        "## Mean completed / economic (valid replays only)",
        "",
        "```json",
        json.dumps(payload["summary"], indent=2),
        "```",
        "",
        "## Paired CSS-MPC vs baselines",
        "",
        "```json",
        json.dumps(payload["paired"], indent=2),
        "```",
        "",
        "## Infinite-battery (rebuilt arcs)",
        "",
        "```json",
        json.dumps(payload.get("infinite_battery_summary", {}), indent=2),
        "```",
        "",
        "Reproduce: `python -m safe_time_evrp.mpc_central.mpc_development_eval`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def _write_terminal_doc() -> None:
    text = (
        "# MPC terminal feasibility validation\n\n"
        "## Predicate separation\n\n"
        "| Check | Module | Meaning |\n"
        "|---|---|---|\n"
        "| Stage-0 commitment | `validate_continuation` | Covers obligations **now** |\n"
        "| Horizon-end terminal | `project_to_horizon` + `verify_terminal_commitment` "
        "| Feasible suffix at horizon end |\n\n"
        "## Rejection taxonomy\n\n"
        "- `terminal_infeasible` — terminal state not in X_f\n"
        "- `rollout_failed` / `replay_failed` — projection invalid\n"
        "- `budget` — cooperative deadline during projection\n\n"
        "## Gate-2 evidence\n\n"
        "Automated tests in `tests/test_css_mpc_gates_1_to_4.py`:\n\n"
        "- `test_gate2_verify_terminal_rejects_stranded_obligation`\n"
        "- `test_gate2_stage0_pass_terminal_constraint_is_distinct`\n\n"
        "Constructed stranded terminal states with insufficient SoC fail "
        "`verify_terminal_commitment` even when a healthy stage-0 full route on a "
        "different start state is evaluated separately.\n\n"
        "## Controller integration\n\n"
        "`CommitmentSafeStochasticMpc._terminal_filter` rejects candidates that fail "
        "terminal checks on any scored scenario before soft objective ranking.\n"
    )
    OUT_TERM.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    payload = run_development()
    print(json.dumps({"gate": payload["development_gate"], "summary": payload["summary"]}, indent=2))
