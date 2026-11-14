"""Schneider-derived dynamic EVRPTW evaluation (controllers unchanged).

Compares B1, M1, stochastic MPC, CC-E-MPC, and CC-E-MPC without forecasts under
matched environment realizations. Does not retune objectives or ALNS budgets
relative to the synthetic closeout package defaults.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import (
    BENCHMARK_LABEL,
    DYNAMICITY_SPECS,
    PROTOCOL_VERSION,
    Dynamicity,
    build_dynamic_episode,
    environment_seed_for,
    list_schneider_refs,
    load_instance,
    policy_seed_for,
    require_verified_schneider_archive,
    scalability_instance_stems,
    stratified_split_small,
)
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, build_anonymous_scenarios, fit_empirical_arrivals
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.validation.replay import validate_log

# Same evaluation budget as synthetic closeout (not retuned for Schneider scores).
ALNS_ITERATIONS = 10
ALNS_TIME_SECONDS = 0.35
N_SCENARIOS = 2
CUSTOMERS_PER_SCENARIO = 2
ANNOUNCEMENT_MEAN = 12.0
ROLLOUT_MAX_EVENTS = 200
ENV_REALIZATIONS_MAIN = 5
CONTROLLER_NAMES = ("b1", "m1", "stochastic_mpc", "cce_mpc", "cce_no_forecast")

# Smoke tier: one stem per size bucket, medium dynamicity, 2 env realizations.
SMOKE_STEMS = ("c101C5", "r201C10", "rc202C15")
# Scalability: short wall budget; report timeout/infeasibility without substitution.
SCALE_ALNS_TIME = 0.35
SCALE_MAX_EVENTS = 8_000


def fit_schneider_train_forecast(
    train_stems: list[str],
    *,
    seed: int,
    n_scenarios: int = N_SCENARIOS,
    customers_per_scenario: int = CUSTOMERS_PER_SCENARIO,
    announcement_mean: float = ANNOUNCEMENT_MEAN,
) -> ArrivalForecast:
    instances = [load_instance(stem) for stem in train_stems]
    model = fit_empirical_arrivals(instances)
    return build_anonymous_scenarios(
        model,
        n_scenarios=n_scenarios,
        customers_per_scenario=customers_per_scenario,
        seed=stable_seed("schneider_dyn_train_forecast", str(seed), PROTOCOL_VERSION),
        announcement_mean=announcement_mean,
    )


def _build_controllers(case, forecast: ArrivalForecast, *, policy_seed: int):
    common = dict(
        alns_iterations=ALNS_ITERATIONS,
        time_limit_seconds=ALNS_TIME_SECONDS,
        seed=policy_seed,
    )
    return {
        "b1": FullValidationAlnsMpc(
            case.instance,
            case.horizon,
            iterations=ALNS_ITERATIONS,
            time_limit_seconds=ALNS_TIME_SECONDS,
            seed=policy_seed,
        ),
        "m1": CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=ALNS_ITERATIONS,
            time_limit_seconds=ALNS_TIME_SECONDS,
            seed=policy_seed,
        ),
        "stochastic_mpc": CommitmentSafePredictiveMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_counterfactuals=True,
            use_forecast=True,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=ROLLOUT_MAX_EVENTS,
            allocation="uniform",
            **common,
        ),
        "cce_mpc": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_forecast=True,
            use_persistent_certificate=True,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=ROLLOUT_MAX_EVENTS,
            **common,
        ),
        "cce_no_forecast": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=ROLLOUT_MAX_EVENTS,
            **common,
        ),
    }


def _summarize_episode(case, name: str, result, ctrl, *, wall_seconds: float) -> dict:
    report = validate_log(case.instance, result.log)
    final = result.final_requests
    cert_status = getattr(ctrl, "last_validation_status", None)
    first_action_changes = 0
    prev_key = None
    for d in result.decisions:
        key = (
            tuple(d.newly_accepted),
            tuple(d.rejected),
            tuple(tuple(v.node_id for v in route) for route in (d.routes or {}).values()),
        )
        if prev_key is not None and key != prev_key:
            first_action_changes += 1
        prev_key = key
    failure = None
    if not report.ok:
        failure = f"replay_invalid:{report.code}"
    elif result.termination_reason in {"event_budget", "t_max"} and any(st == "accepted" for st in final.values()):
        failure = f"horizon_cutoff:{result.termination_reason}"
    return {
        "controller": name,
        "failure": failure,
        "completed_count": sum(1 for st in final.values() if st == "completed"),
        "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
        "rejected_count": sum(1 for st in final.values() if st == "rejected"),
        "accepted_open_count": sum(1 for st in final.values() if st == "accepted"),
        "executed_distance": executed_distance_from_log(case.instance, result.log),
        "charge_starts": sum(1 for rec in result.log if rec.kind == "charge_start"),
        "optimize_seconds": result.optimize_seconds,
        "wall_seconds": wall_seconds,
        "fallback_count": result.fallback_count,
        "no_feasible_continuation_count": result.no_feasible_continuation_count,
        "termination_reason": result.termination_reason,
        "replay_ok": report.ok,
        "replay_code": report.code,
        "certificate_status_last": cert_status,
        "deadline_overruns": getattr(getattr(ctrl, "profile", None), "deadline_overruns", None),
        "first_action_change_count": first_action_changes,
        "n_decisions": len(result.decisions),
        "overtime": bool(
            getattr(getattr(ctrl, "profile", None), "deadline_overruns", 0)
            and getattr(ctrl.profile, "deadline_overruns", 0) > 0
        ),
    }


def evaluate_episode(
    stem: str,
    *,
    realization_index: int,
    dynamicity: str,
    split: str,
    forecast: ArrivalForecast,
    controller_names: tuple[str, ...] = CONTROLLER_NAMES,
    max_events: int = 20_000,
    alns_time: float | None = None,
) -> dict:
    env_seed = environment_seed_for(stem, realization_index)
    # Shared policy seed across controllers for this realization.
    pol_seed = policy_seed_for(stem, realization_index, "shared")
    episode = build_dynamic_episode(
        stem,
        environment_seed=env_seed,
        policy_seed=pol_seed,
        dynamicity=dynamicity,
        split=split,
    )
    case = episode.case
    controllers = _build_controllers(case, forecast, policy_seed=pol_seed)
    if alns_time is not None:
        for ctrl in controllers.values():
            if hasattr(ctrl, "time_limit_seconds"):
                ctrl.time_limit_seconds = alns_time
    cell = {
        "episode_id": episode.episode_id,
        "instance_stem": stem,
        "family": episode.family,
        "n_customers": episode.n_customers,
        "dynamicity": episode.dynamicity,
        "split": split,
        "environment_seed": env_seed,
        "policy_seed": pol_seed,
        "realization_index": realization_index,
        "fleet_size": episode.fleet_size,
        "fleet_rule": episode.fleet_rule,
        "horizon": episode.horizon,
        "release_rule": episode.release_rule,
        "known_at_start": list(episode.known_at_start),
        "dynamic_arrivals": list(episode.dynamic_arrivals),
        "releases": [{"customer_id": c, "t": t} for c, t in episode.releases],
        "instance_hash": episode.instance_hash,
        "controllers": {},
        "paired": {},
    }
    for name in controller_names:
        ctrl = controllers[name]
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
                max_events=max_events,
            )
            wall = time.perf_counter() - t0
            cell["controllers"][name] = _summarize_episode(case, name, result, ctrl, wall_seconds=wall)
        except Exception as exc:  # noqa: BLE001
            wall = time.perf_counter() - t0
            cell["controllers"][name] = {
                "controller": name,
                "failure": f"exception:{type(exc).__name__}:{exc}",
                "wall_seconds": wall,
                "replay_ok": False,
                "completed_count": None,
                "accepted_unfulfilled_count": None,
                "rejected_count": None,
            }
    # Paired differences vs B1 / stochastic (only when both completed metrics exist)
    b1 = cell["controllers"].get("b1", {})
    for name in controller_names:
        row = cell["controllers"][name]
        if row.get("completed_count") is None or b1.get("completed_count") is None:
            continue
        cell["paired"][f"{name}_minus_b1_completed"] = row["completed_count"] - b1["completed_count"]
        cell["paired"][f"{name}_minus_b1_au"] = row["accepted_unfulfilled_count"] - b1["accepted_unfulfilled_count"]
    stoch = cell["controllers"].get("stochastic_mpc", {})
    cce = cell["controllers"].get("cce_mpc", {})
    if cce.get("completed_count") is not None and stoch.get("completed_count") is not None:
        cell["paired"]["cce_minus_stoch_completed"] = cce["completed_count"] - stoch["completed_count"]
        cell["paired"]["cce_equals_stoch"] = (
            cce["completed_count"] == stoch["completed_count"]
            and cce["accepted_unfulfilled_count"] == stoch["accepted_unfulfilled_count"]
        )
    return cell


def _mean_ci(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "std": None, "ci95_halfwidth": None}
    m = mean(values)
    if len(values) == 1:
        return {"n": 1, "mean": m, "std": 0.0, "ci95_halfwidth": 0.0}
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    std = math.sqrt(var)
    # Normal approx; n small — reported honestly as approx.
    half = 1.96 * std / math.sqrt(len(values))
    return {"n": len(values), "mean": m, "std": std, "ci95_halfwidth": half}


def analyze_rows(rows: list[dict]) -> dict:
    by_ctrl: dict[str, list[float]] = defaultdict(list)
    paired_cce_b1: list[float] = []
    paired_cce_stoch: list[float] = []
    failures: dict[str, int] = defaultdict(int)
    by_size: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_family: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_dyn: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        for name, ctrl in row["controllers"].items():
            if ctrl.get("failure"):
                failures[f"{name}:{ctrl['failure'].split(':')[0]}"] += 1
            if ctrl.get("completed_count") is None:
                continue
            by_ctrl[name].append(float(ctrl["completed_count"]))
            by_size[str(row["n_customers"])][name].append(float(ctrl["completed_count"]))
            by_family[row["family"]][name].append(float(ctrl["completed_count"]))
            by_dyn[row["dynamicity"]][name].append(float(ctrl["completed_count"]))
        paired = row.get("paired", {})
        if "cce_mpc_minus_b1_completed" in paired:
            paired_cce_b1.append(float(paired["cce_mpc_minus_b1_completed"]))
        if "cce_minus_stoch_completed" in paired:
            paired_cce_stoch.append(float(paired["cce_minus_stoch_completed"]))
    return {
        "completed_by_controller": {k: _mean_ci(v) for k, v in by_ctrl.items()},
        "paired_cce_minus_b1_completed": _mean_ci(paired_cce_b1),
        "paired_cce_minus_stoch_completed": _mean_ci(paired_cce_stoch),
        "failure_counts": dict(failures),
        "completed_by_size": {sz: {c: _mean_ci(vs) for c, vs in ctrls.items()} for sz, ctrls in by_size.items()},
        "completed_by_family": {f: {c: _mean_ci(vs) for c, vs in ctrls.items()} for f, ctrls in by_family.items()},
        "completed_by_dynamicity": {d: {c: _mean_ci(vs) for c, vs in ctrls.items()} for d, ctrls in by_dyn.items()},
        "n_rows": len(rows),
    }


def build_manifest() -> dict:
    require_verified_schneider_archive()
    splits = stratified_split_small()
    small = list_schneider_refs(sizes=(5, 10, 15))
    return {
        "benchmark_label": BENCHMARK_LABEL,
        "protocol_version": PROTOCOL_VERSION,
        "schneider_deposit": "10.17632/h3mrm5dhxw.1",
        "dynamicity_specs": DYNAMICITY_SPECS,
        "splits_by_base_instance": splits,
        "small_instance_stems": [r.stem for r in small],
        "n_small_instances": len(small),
        "environment_realizations_main": ENV_REALIZATIONS_MAIN,
        "smoke_stems": list(SMOKE_STEMS),
        "scalability_stems_predeclared": list(scalability_instance_stems()),
        "controllers": list(CONTROLLER_NAMES),
        "evaluation_budget": {
            "alns_iterations": ALNS_ITERATIONS,
            "alns_time_seconds": ALNS_TIME_SECONDS,
            "n_scenarios": N_SCENARIOS,
            "customers_per_scenario": CUSTOMERS_PER_SCENARIO,
            "announcement_mean_forecast": ANNOUNCEMENT_MEAN,
            "rollout_max_events": ROLLOUT_MAX_EVENTS,
            "note": "Matched to synthetic closeout package; not retuned on Schneider scores.",
        },
        "seed_semantics": {
            "environment_seed": "draws announcement realization only",
            "policy_seed": "controller/ALNS/forecast RNG; shared across paired controllers",
        },
        "previous_synthetic_holdout": {
            "case": "B_adversarial_overaccept",
            "status": "already_evaluated_do_not_present_as_fresh",
        },
        "forecast_rule": "fit_empirical_arrivals on Schneider train stems only; anonymous scenarios",
    }


def run_tier(
    tier: str,
    *,
    dynamicity: str = Dynamicity.MEDIUM.value,
    out_json: Path | None = None,
) -> dict:
    require_verified_schneider_archive()
    splits = stratified_split_small()
    stem_to_split = {s: "train" for s in splits["train"]}
    stem_to_split.update({s: "development" for s in splits["development"]})
    stem_to_split.update({s: "test" for s in splits["test"]})

    forecast = fit_schneider_train_forecast(splits["train"], seed=0)
    rows: list[dict] = []
    meta: dict = {"tier": tier, "dynamicity": dynamicity, "protocol_version": PROTOCOL_VERSION}

    if tier == "smoke":
        stems = list(SMOKE_STEMS)
        n_env = 2
        max_events = 20_000
        alns_time = None
    elif tier == "small":
        stems = [r.stem for r in list_schneider_refs(sizes=(5, 10, 15))]
        n_env = ENV_REALIZATIONS_MAIN
        max_events = 20_000
        alns_time = None
    elif tier == "scale":
        stems = list(scalability_instance_stems())
        n_env = 1
        max_events = SCALE_MAX_EVENTS
        alns_time = SCALE_ALNS_TIME
        # Confirm stems exist among 100-customer files
        available = {r.stem for r in list_schneider_refs(sizes=(100,))}
        missing = [s for s in stems if s not in available]
        if missing:
            raise FileNotFoundError(f"predeclared scalability stems missing: {missing}")
    else:
        raise ValueError(f"unknown tier {tier}")

    meta.update({"stems": stems, "n_env": n_env, "alns_time": alns_time or ALNS_TIME_SECONDS})
    t_start = time.perf_counter()
    for stem in stems:
        split = stem_to_split.get(stem, "scalability" if tier == "scale" else "unassigned")
        for ridx in range(n_env):
            rows.append(
                evaluate_episode(
                    stem,
                    realization_index=ridx,
                    dynamicity=dynamicity,
                    split=split,
                    forecast=forecast,
                    max_events=max_events,
                    alns_time=alns_time,
                )
            )
    analysis = analyze_rows(rows)
    payload = {
        "manifest": build_manifest(),
        "run_meta": {**meta, "wall_seconds_total": time.perf_counter() - t_start},
        "analysis": analysis,
        "rows": rows,
    }
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_analysis_markdown(payload: dict, path: Path) -> None:
    a = payload["analysis"]
    meta = payload["run_meta"]
    lines = [
        "# Schneider-derived dynamic EVRPTW — results analysis",
        "",
        f"**Benchmark:** {BENCHMARK_LABEL}  ",
        f"**Protocol:** `{PROTOCOL_VERSION}`  ",
        f"**Tier:** `{meta.get('tier')}`  ",
        f"**Dynamicity:** `{meta.get('dynamicity')}`  ",
        f"**Rows:** {a.get('n_rows')}  ",
        f"**Wall seconds (runner):** {meta.get('wall_seconds_total')}  ",
        "",
        "## Controllers (unchanged)",
        "",
        ", ".join(CONTROLLER_NAMES),
        "",
        "## Mean completed services",
        "",
    ]
    for name, stats in a.get("completed_by_controller", {}).items():
        lines.append(
            f"- **{name}**: mean={stats['mean']}, n={stats['n']}, approx 95% CI half-width={stats['ci95_halfwidth']}"
        )
    lines += [
        "",
        "## Paired differences (CC-E-MPC)",
        "",
        f"- vs B1 completed: {a.get('paired_cce_minus_b1_completed')}",
        f"- vs stochastic MPC completed: {a.get('paired_cce_minus_stoch_completed')}",
        "",
        "## Failures",
        "",
        f"```json\n{json.dumps(a.get('failure_counts', {}), indent=2)}\n```",
        "",
        "## By customer count",
        "",
        f"```json\n{json.dumps(a.get('completed_by_size', {}), indent=2)}\n```",
        "",
        "## By family",
        "",
        f"```json\n{json.dumps(a.get('completed_by_family', {}), indent=2)}\n```",
        "",
        "## Scientific reading",
        "",
        "This analysis does not retune controllers. Stronger or weaker mean completed-service",
        "gaps versus B1/M1/stochastic MPC on Schneider-derived episodes should be read as",
        "evidence quality for the existing `INCREMENTAL_RESULT` assessment, not as a new method claim.",
        "",
        "The prior synthetic holdout `B_adversarial_overaccept` remains already-evaluated and is",
        "not presented as fresh unseen validation.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("smoke", "small", "scale"), default="smoke")
    parser.add_argument("--dynamicity", choices=tuple(DYNAMICITY_SPECS), default="medium")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json"),
    )
    parser.add_argument(
        "--analysis",
        type=Path,
        default=Path("docs/experiments/SCHNEIDER_DYNAMIC_ANALYSIS.md"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/reproducibility/DYNAMIC_BENCHMARK_MANIFEST.json"),
    )
    args = parser.parse_args(argv)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(build_manifest(), indent=2), encoding="utf-8")
    payload = run_tier(args.tier, dynamicity=args.dynamicity, out_json=args.out)
    write_analysis_markdown(payload, args.analysis)
    print(json.dumps({"tier": args.tier, "n_rows": payload["analysis"]["n_rows"], "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
