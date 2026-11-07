"""Gate 3F middle-regime diagnostic under repaired arrival semantics."""

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
from safe_time_evrp.mpc3c.controllers import CONTROLLER_LABELS
from safe_time_evrp.mpc3c.forecast import (
    build_anonymous_scenarios,
    fit_empirical_arrivals,
    forecast_seed_for,
    release_seed_for,
    synthetic_poisson_releases,
)
from safe_time_evrp.mpc3c.seeds import instance_content_hash
from safe_time_evrp.mpc3c.sim_experiment import compare_controllers
from safe_time_evrp.mpc3c.upper_bound import is_middle_regime, offline_service_upper_bound

OUT = Path("docs/research_gate_3f")


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seeds_path = Path("docs/research_gate_3c/evrptwd_seeds.json")
    payload = json.loads(seeds_path.read_text(encoding="utf-8"))
    splits = payload["splits"]
    seed_index = {rec["file"]: rec for rec in payload.get("records", [])}
    root = extract_root(Path("data/raw/evrp_tw_d"))

    train_inst = []
    for name in splits["Cus_5"]["train"][:12]:
        rec = seed_index.get(name)
        if not rec or not rec.get("feasible"):
            continue
        train_inst.append(
            parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        )
    arrival_model = fit_empirical_arrivals(train_inst)
    day_horizon = max(
        (float(n.window.due) for inst in train_inst for n in inst.customers),
        default=200.0,
    )

    results: dict = {
        "git_commit": _git_commit(),
        "controller_labels": {k.value: v for k, v in CONTROLLER_LABELS.items()},
        "forecast_model_id": arrival_model.model_id,
        "stochastic_claim": "single_scenario_anticipatory_only",
        "evrptwd_candidates": [],
        "evrptwd_middle_regime": [],
        "amazon": [],
    }

    # Probe rate scales of the train interarrival mean; select middle-regime by
    # announcement-aware offline upper bound (not a fabricated battery shrink).
    base_mu = arrival_model.train_interarrival_mean or 1.0
    for name in splits["Cus_5"]["dev"][:20]:
        rec = seed_index.get(name)
        if not rec or not rec.get("feasible"):
            continue
        fleet = int(rec["fleet_size"])
        inst = parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        chosen = None
        # Train ready-gap mu is often << window times; larger scales create late
        # announcements that the announcement-aware upper bound can classify as mid-regime.
        for scale in (1.0, 5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 30.0):
            releases = synthetic_poisson_releases(
                inst,
                seed=release_seed_for(f"{name}|mu_scale={scale}"),
                mean_interarrival=base_mu * scale,
            )
            ub = offline_service_upper_bound(inst, releases, fleet_size=fleet)
            entry = {
                "file": name,
                "fleet_size": fleet,
                "mu_scale": scale,
                "mean_interarrival": base_mu * scale,
                "upper_bound": ub.__dict__,
                "middle_regime": is_middle_regime(ub),
                "release_seed": release_seed_for(f"{name}|mu_scale={scale}"),
                "instance_hash": instance_content_hash(inst),
            }
            results["evrptwd_candidates"].append(entry)
            if chosen is None and is_middle_regime(ub):
                chosen = (releases, entry)
        if chosen is None or len(results["evrptwd_middle_regime"]) >= 4:
            continue
        releases, entry = chosen
        forecast = build_anonymous_scenarios(
            arrival_model,
            n_scenarios=3,
            customers_per_scenario=2,
            seed=forecast_seed_for(name),
            day_horizon=day_horizon,
        )
        report = compare_controllers(
            inst,
            fleet_size=fleet,
            horizon=12.0,
            releases=releases,
            forecast=forecast,
        )
        report.update(entry)
        report["releases"] = releases
        results["evrptwd_middle_regime"].append(report)

    try:
        route_ids = list_route_ids()[:3]
    except FileNotFoundError:
        route_ids = []
    for rid in route_ids:
        for cfg in (ESOGU_LIGHT_CARGO_V1, ESOGU_ENERGY_ACTIVE_V1):
            inst = load_amazon_route(rid, max_customers=10, electrification=cfg)
            releases = [(cid, float(inst.node(cid).window.ready)) for cid in inst.customer_ids()]
            ub = offline_service_upper_bound(inst, releases, fleet_size=1)
            forecast = build_anonymous_scenarios(
                arrival_model,
                n_scenarios=2,
                customers_per_scenario=2,
                seed=forecast_seed_for(rid + cfg.name),
                day_horizon=cfg.day_horizon_h,
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
                    "window_conflicts_excluded": inst.metadata.get("window_conflicts_excluded"),
                    "upper_bound": ub.__dict__,
                    "instance_hash": instance_content_hash(inst),
                }
            )
            results["amazon"].append(report)

    (OUT / "matched_diagnostic.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    def _agg(pool: list[dict]) -> dict:
        usable = [r for r in pool if "results" in r]
        if not usable:
            return {"n": 0}
        ctrls = list(usable[0]["results"])
        return {
            "n": len(usable),
            "mean_served": {c: sum(r["results"][c]["n_served"] for r in usable) / len(usable) for c in ctrls},
            "mean_service_rate": {c: sum(r["results"][c]["service_rate"] for r in usable) / len(usable) for c in ctrls},
            "mean_ub_rate": sum(r["upper_bound"]["static_service_rate"] for r in usable) / len(usable),
            "flex_equals_rollout_frac": sum(1 for r in usable if r.get("flex_equals_rollout_sequence")) / len(usable),
            "mean_commitment_violations": {
                c: sum(r["results"][c]["commitment_violations"] for r in usable) / len(usable) for c in ctrls
            },
        }

    summary = {
        "git_commit": results["git_commit"],
        "n_candidates_probed": len(results["evrptwd_candidates"]),
        "n_middle_regime": len(results["evrptwd_middle_regime"]),
        "evrptwd_middle_regime": _agg(results["evrptwd_middle_regime"]),
        "amazon_light": _agg([r for r in results["amazon"] if r.get("electrification") == ESOGU_LIGHT_CARGO_V1.name]),
        "amazon_energy_active": _agg(
            [r for r in results["amazon"] if r.get("electrification") == ESOGU_ENERGY_ACTIVE_V1.name]
        ),
        "controller_labels": results["controller_labels"],
        "stochastic_claim": results["stochastic_claim"],
    }
    (OUT / "matched_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
