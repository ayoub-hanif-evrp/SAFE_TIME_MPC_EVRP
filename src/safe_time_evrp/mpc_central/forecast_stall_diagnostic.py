"""Controlled diagnostic: stall repair check + forecast misspecification vs calibration.

Fixed representative Schneider sample chosen **before** inspecting controller win rates
(alphabetical C/R/RC × 5/10/15). Protocol v2 releases. Controllers unchanged.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    PROTOCOL_VERSION_V2,
    build_dynamic_episode_v2,
    calibrated_announcement_mean_from_train,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, build_anonymous_scenarios, fit_empirical_arrivals
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.scenario_rollout import rollout_candidate
from safe_time_evrp.validation.replay import validate_log

# Predeclared diagnostic sample (not selected by prior wins).
DIAGNOSTIC_STEMS: tuple[str, ...] = (
    "c101C5",
    "c104C10",
    "c106C15",
    "r104C5",
    "r103C10",
    "r105C15",
    "rc105C5",
    "rc108C10",
    "rc108C15",
)
ENV_REALIZATIONS = 2
ALNS_ITERATIONS = 10
ALNS_TIME = 0.35
N_SCENARIOS = 2
MISSPECIFIED_MEAN = 12.0


def _forecast(train_stems: list[str], *, seed: int, announcement_mean: float) -> ArrivalForecast:
    model = fit_empirical_arrivals([load_instance(s) for s in train_stems])
    return build_anonymous_scenarios(
        model,
        n_scenarios=N_SCENARIOS,
        customers_per_scenario=2,
        seed=stable_seed("diag_forecast", str(seed), PROTOCOL_VERSION_V2, f"mu={announcement_mean}"),
        announcement_mean=announcement_mean,
    )


def _controllers(case, forecast: ArrivalForecast | None, *, policy_seed: int, use_forecast: bool):
    common = dict(alns_iterations=ALNS_ITERATIONS, time_limit_seconds=ALNS_TIME, seed=policy_seed)
    out = {
        "b1": FullValidationAlnsMpc(
            case.instance,
            case.horizon,
            iterations=ALNS_ITERATIONS,
            time_limit_seconds=ALNS_TIME,
            seed=policy_seed,
        ),
        "m1": CertificateCarryingAlnsMpc(
            case.instance,
            case.horizon,
            iterations=ALNS_ITERATIONS,
            time_limit_seconds=ALNS_TIME,
            seed=policy_seed,
        ),
        "cce_no_forecast": CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_forecast=False,
            use_persistent_certificate=True,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=200,
            **common,
        ),
    }
    if forecast is not None:
        out["stochastic_mpc"] = CommitmentSafePredictiveMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_counterfactuals=True,
            use_forecast=use_forecast,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=200,
            allocation="uniform",
            **common,
        )
        out["cce_mpc"] = CertificateCarryingEconomicMpc(
            case.instance,
            case.horizon,
            forecast=forecast,
            n_scenarios=N_SCENARIOS,
            use_forecast=use_forecast,
            use_persistent_certificate=True,
            max_replan_interval=case.max_replan_interval,
            rollout_max_events=200,
            **common,
        )
    return out


def _run_one(case, ctrl, name: str) -> dict:
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
        wall = time.perf_counter() - t0
        rep = validate_log(case.instance, result.log)
        final = result.final_requests
        return {
            "controller": name,
            "failure": None if rep.ok else f"replay_invalid:{rep.code}",
            "stall": False,
            "completed_count": sum(1 for st in final.values() if st == "completed"),
            "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
            "rejected_count": sum(1 for st in final.values() if st == "rejected"),
            "executed_distance": executed_distance_from_log(case.instance, result.log),
            "optimize_seconds": result.optimize_seconds,
            "wall_seconds": wall,
            "termination_reason": result.termination_reason,
            "replay_ok": rep.ok,
            "n_decisions": len(result.decisions),
        }
    except Exception as exc:  # noqa: BLE001
        wall = time.perf_counter() - t0
        msg = f"{type(exc).__name__}:{exc}"
        return {
            "controller": name,
            "failure": msg,
            "stall": "decision loop did not advance time" in msg,
            "wall_seconds": wall,
            "completed_count": None,
            "replay_ok": False,
        }


def release_statistics_diagnostic(episode, classifications) -> dict:
    """Release-history summary only — not a perfect-information oracle."""
    return {
        "label": "release_statistics_diagnostic",
        "n_releases": len(episode.releases),
        "n_late_for_depot_admit": sum(1 for c in classifications if c.late_for_depot_admit),
        "note": (
            "Not a perfect-information oracle and not a deployable controller. "
            "Records realized release statistics only; no hindsight decisions/values."
        ),
        "rollout_candidate_available": callable(rollout_candidate),
    }


# Backward-compatible alias (deprecated name).
_perfect_info_diagnostic = release_statistics_diagnostic


def run_diagnostic(*, out_json: Path | None = None, out_md: Path | None = None) -> dict:
    splits = stratified_split_small()
    # Ensure diagnostic stems are not chosen by prior wins; verify membership only.
    all_small = set(splits["train"] + splits["development"] + splits["test"])
    missing = [s for s in DIAGNOSTIC_STEMS if s not in all_small]
    if missing:
        raise RuntimeError(f"diagnostic stems not in Schneider small set: {missing}")

    calib = calibrated_announcement_mean_from_train(splits["train"], dynamicity="medium", n_realizations=3)
    mu_hat = float(calib["calibrated_announcement_mean"])
    forecast_miss = _forecast(splits["train"], seed=0, announcement_mean=MISSPECIFIED_MEAN)
    forecast_cal = _forecast(splits["train"], seed=1, announcement_mean=mu_hat)

    rows: list[dict] = []
    stall_count = 0
    for stem in DIAGNOSTIC_STEMS:
        split = "train" if stem in splits["train"] else "development" if stem in splits["development"] else "test"
        for ridx in range(ENV_REALIZATIONS):
            env = (environment_seed_for(stem, ridx) ^ 0xA5A5A5) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, classifications, fleet_meta = build_dynamic_episode_v2(
                stem,
                environment_seed=env,
                policy_seed=pol,
                dynamicity="medium",
                split=split,
            )
            case = episode.case
            cell = {
                "stem": stem,
                "split": split,
                "realization_index": ridx,
                "environment_seed": env,
                "policy_seed": pol,
                "fleet_size": episode.fleet_size,
                "fleet_meta": fleet_meta,
                "n_late_for_depot_admit": sum(1 for c in classifications if c.late_for_depot_admit),
                "n_customers": episode.n_customers,
                "family": episode.family,
                "variants": {},
                "release_statistics_diagnostic": release_statistics_diagnostic(
                    episode, classifications
                ),
            }
            variants = {
                "misspecified_forecast_mu12": (forecast_miss, True),
                "calibrated_forecast": (forecast_cal, True),
                "no_forecast_bundle": (forecast_cal, False),  # forecast object unused when flag False
            }
            for vname, (fc, use_fc) in variants.items():
                ctrls = _controllers(case, fc, policy_seed=pol, use_forecast=use_fc)
                # For no_forecast_bundle run b1/m1/cce_no_forecast + cce with use_forecast False already
                names = (
                    ("b1", "m1", "cce_no_forecast", "cce_mpc", "stochastic_mpc")
                    if use_fc
                    else ("b1", "m1", "cce_no_forecast")
                )
                block = {}
                for name in names:
                    if name not in ctrls:
                        continue
                    summary = _run_one(case, ctrls[name], name)
                    if summary.get("stall"):
                        stall_count += 1
                    block[name] = summary
                cell["variants"][vname] = block
            rows.append(cell)

    # Summaries
    def _collect(variant: str, controller: str, field: str) -> list[float]:
        vals = []
        for row in rows:
            block = row["variants"].get(variant, {})
            cell = block.get(controller)
            if cell and cell.get(field) is not None:
                vals.append(float(cell[field]))
        return vals

    summary = {
        "protocol_version": PROTOCOL_VERSION_V2,
        "diagnostic_stems": list(DIAGNOSTIC_STEMS),
        "env_realizations": ENV_REALIZATIONS,
        "calibration": calib,
        "stall_count": stall_count,
        "n_rows": len(rows),
        "mean_completed": {
            "misspecified_cce": _mean(_collect("misspecified_forecast_mu12", "cce_mpc", "completed_count")),
            "calibrated_cce": _mean(_collect("calibrated_forecast", "cce_mpc", "completed_count")),
            "cce_no_forecast": _mean(_collect("no_forecast_bundle", "cce_no_forecast", "completed_count")),
            "b1": _mean(_collect("misspecified_forecast_mu12", "b1", "completed_count")),
            "m1": _mean(_collect("misspecified_forecast_mu12", "m1", "completed_count")),
            "stochastic_misspecified": _mean(
                _collect("misspecified_forecast_mu12", "stochastic_mpc", "completed_count")
            ),
            "stochastic_calibrated": _mean(_collect("calibrated_forecast", "stochastic_mpc", "completed_count")),
        },
        "failure_flags": _failure_tally(rows),
    }
    payload = {"summary": summary, "rows": rows}
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if out_md is not None:
        out_md.write_text(_render_md(payload), encoding="utf-8")
    return payload


def _mean(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "mean": None}
    return {"n": len(vals), "mean": sum(vals) / len(vals)}


def _failure_tally(rows: list[dict]) -> dict[str, int]:
    tallies: dict[str, int] = {}
    for row in rows:
        for vname, block in row["variants"].items():
            for cname, cell in block.items():
                if cell.get("failure"):
                    key = f"{vname}:{cname}:{str(cell['failure']).split(':')[0]}"
                    tallies[key] = tallies.get(key, 0) + 1
                if cell.get("stall"):
                    tallies["stall_total"] = tallies.get("stall_total", 0) + 1
    return tallies


def _render_md(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        "# Forecast and stall diagnostic",
        "",
        f"**Protocol:** `{s['protocol_version']}`  ",
        f"**Stems:** {', '.join(s['diagnostic_stems'])}  ",
        f"**Environment realizations per stem:** {s['env_realizations']}  ",
        f"**Stall count:** {s['stall_count']}  ",
        "",
        "## Calibration (train-only)",
        "",
        f"```json\n{json.dumps(s['calibration'], indent=2)}\n```",
        "",
        "## Mean completed services",
        "",
        f"```json\n{json.dumps(s['mean_completed'], indent=2)}\n```",
        "",
        "## Failures",
        "",
        f"```json\n{json.dumps(s['failure_flags'], indent=2)}\n```",
        "",
        "## Reading",
        "",
        "- Stall target: **zero** unexplained `decision loop did not advance time` after the",
        "  instantaneous-arc simulator repair.",
        "- Compare misspecified μ=12 vs calibrated μ vs no-forecast under matched seeds.",
        "- Perfect-information block is diagnostic only and non-deployable.",
        "- Prior 36×5 v1 Schneider results remain frozen; this sample is not fresh final validation.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    out_json = Path("docs/experiments/forecast_stall_diagnostic.json")
    out_md = Path("docs/experiments/FORECAST_AND_STALL_DIAGNOSTIC.md")
    payload = run_diagnostic(out_json=out_json, out_md=out_md)
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
