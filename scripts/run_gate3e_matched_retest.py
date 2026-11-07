"""Gate 3E matched development retest under corrected scientific contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from safe_time_evrp.data.amazon import (
    ESOGU_ENERGY_ACTIVE_V1,
    ESOGU_LIGHT_CARGO_V1,
    list_route_ids,
    load_amazon_route,
)
from safe_time_evrp.data.evrp_tw_d import extract_root, parse_solomon_file
from safe_time_evrp.mpc3c.controllers import CONTROLLER_LABELS, ControllerKind
from safe_time_evrp.mpc3c.forecast import (
    build_anonymous_scenarios,
    fit_empirical_arrivals,
    forecast_seed_for,
    release_seed_for,
    synthetic_poisson_releases,
)  # build_scenarios_for(instance=...) quarantined in Gate 3F
from safe_time_evrp.mpc3c.horizon_microscope import search_horizon_causality
from safe_time_evrp.mpc3c.seeds import instance_content_hash
from safe_time_evrp.mpc3c.sim_experiment import compare_controllers, run_sim_dynamic

OUT = Path("docs/research_gate_3e")


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _seed_index(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {rec["file"]: rec for rec in payload.get("records", [])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seeds_path = Path("docs/research_gate_3c/evrptwd_seeds.json")
    payload = json.loads(seeds_path.read_text(encoding="utf-8"))
    splits = payload["splits"]
    seed_index = _seed_index(seeds_path)
    root = extract_root(Path("data/raw/evrp_tw_d"))

    train_inst = []
    for name in splits["Cus_5"]["train"][:12]:
        rec = seed_index.get(name)
        if rec is None or not rec.get("feasible"):
            continue
        train_inst.append(
            parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        )
    arrival_model = fit_empirical_arrivals(train_inst)

    results: dict = {
        "git_commit": _git_commit(),
        "controller_labels": {k.value: v for k, v in CONTROLLER_LABELS.items()},
        "forecast_model_id": arrival_model.model_id,
        "horizon_microscope": search_horizon_causality(),
        "evrptwd_dev": [],
        "amazon": [],
        "protocol": {
            "forecast": "anonymous_train_atoms_only",
            "seeds": "sha256_stable_seed",
            "fleet": "seed_required_fleet_size",
            "holdout_used_for_tuning": False,
        },
    }

    for name in splits["Cus_5"]["dev"][:4]:
        rec = seed_index.get(name)
        if rec is None or not rec.get("feasible"):
            continue
        fleet = int(rec["fleet_size"])
        inst = parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        rel_seed = release_seed_for(name)
        fc_seed = forecast_seed_for(name)
        releases = synthetic_poisson_releases(
            inst,
            seed=rel_seed,
            mean_interarrival=arrival_model.train_interarrival_mean,
        )
        forecast = build_anonymous_scenarios(
            arrival_model,
            n_scenarios=3,
            customers_per_scenario=2,
            seed=fc_seed,
        )
        report = compare_controllers(
            inst,
            fleet_size=fleet,
            horizon=12.0,
            releases=releases,
            forecast=forecast,
        )
        report.update(
            {
                "file": name,
                "seed_fleet_size": fleet,
                "release_seed": rel_seed,
                "forecast_seed": fc_seed,
                "instance_hash": instance_content_hash(inst),
                "native_Q": rec.get("native_Q"),
                "releases": releases,
            }
        )
        results["evrptwd_dev"].append(report)

    try:
        route_ids = list_route_ids()[:3]
    except FileNotFoundError:
        route_ids = []
    for rid in route_ids:
        # Milder baseline + energy-active for charging relevance comparison.
        for cfg in (ESOGU_LIGHT_CARGO_V1, ESOGU_ENERGY_ACTIVE_V1):
            inst = load_amazon_route(rid, max_customers=10, electrification=cfg)
            releases = [(cid, float(inst.node(cid).window.ready)) for cid in inst.customer_ids()]
            forecast = build_anonymous_scenarios(
                arrival_model,
                n_scenarios=2,
                customers_per_scenario=2,
                seed=forecast_seed_for(rid + cfg.name),
            )
            report = compare_controllers(
                inst,
                fleet_size=1,
                horizon=3.0,
                releases=releases,
                forecast=forecast,
            )
            report.update(
                {
                    "file": rid,
                    "electrification": cfg.name,
                    "consumption_kwh_per_km": cfg.consumption_kwh_per_km,
                    "battery_kwh": cfg.battery_kwh,
                    "charger": "synthetic_depot_colocated",
                    "observed_package_windows": inst.metadata.get("observed_package_windows"),
                    "instance_hash": instance_content_hash(inst),
                    "release_seed": release_seed_for(rid),
                    "forecast_seed": forecast_seed_for(rid + cfg.name),
                }
            )
            results["amazon"].append(report)

    # Trace the Gate 3D commitment failure case under Gate 3E harness.
    held = "solomon_dataset_140_RC_wide_1769114883.txt"
    if held in seed_index:
        rec = seed_index[held]
        inst = parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / held).with_recharge_policy("full")
        releases = synthetic_poisson_releases(
            inst,
            seed=release_seed_for(held),
            mean_interarrival=arrival_model.train_interarrival_mean,
        )
        run = run_sim_dynamic(
            inst,
            ControllerKind.RH_OPEN_LOOP,
            fleet_size=int(rec["fleet_size"]),
            horizon=12.0,
            releases=releases,
            forecast=build_anonymous_scenarios(
                arrival_model, n_scenarios=3, customers_per_scenario=2, seed=forecast_seed_for(held)
            ),
        )
        results["solomon_140_rh_trace"] = {
            "file": held,
            "n_served": len(run.served),
            "commitment_violations": run.commitment_violations,
            "accepted_unfulfilled": run.accepted_unfulfilled,
            "replay_ok": run.replay_ok,
            "executed_first_action_signature": run.executed_first_action_signature,
            "release_seed": release_seed_for(held),
        }

    (OUT / "matched_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    def _agg(pool: list[dict]) -> dict:
        usable = [r for r in pool if "results" in r]
        if not usable:
            return {"n": 0}
        ctrls = list(usable[0]["results"])
        return {
            "n": len(usable),
            "mean_served": {c: sum(r["results"][c]["n_served"] for r in usable) / len(usable) for c in ctrls},
            "mean_service_rate": {
                c: sum(r["results"][c]["service_rate"] for r in usable) / len(usable) for c in ctrls
            },
            "mean_commitment_violations": {
                c: sum(r["results"][c]["commitment_violations"] for r in usable) / len(usable) for c in ctrls
            },
            "flex_equals_rollout_frac": sum(1 for r in usable if r.get("flex_equals_rollout_sequence"))
            / len(usable),
            "replay_ok_frac": sum(
                1 for r in usable if all(r["results"][c]["replay_ok"] for c in ctrls)
            )
            / len(usable),
            "mean_charge_events": {
                c: sum(r["results"][c]["charge_events"] for r in usable) / len(usable) for c in ctrls
            },
        }

    summary = {
        "git_commit": results["git_commit"],
        "evrptwd_dev": _agg(results["evrptwd_dev"]),
        "amazon_light": _agg([r for r in results["amazon"] if r.get("electrification") == ESOGU_LIGHT_CARGO_V1.name]),
        "amazon_energy_active": _agg(
            [r for r in results["amazon"] if r.get("electrification") == ESOGU_ENERGY_ACTIVE_V1.name]
        ),
        "horizon_microscope": results["horizon_microscope"],
        "solomon_140_rh_trace": results.get("solomon_140_rh_trace"),
        "controller_labels": results["controller_labels"],
    }
    (OUT / "matched_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
