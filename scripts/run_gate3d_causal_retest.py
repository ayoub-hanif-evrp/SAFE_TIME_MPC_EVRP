"""Gate 3D matched causal re-test under the repaired simulator harness."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.data.amazon import ESOGU_ENERGY_ACTIVE_V1, list_route_ids, load_amazon_route
from safe_time_evrp.data.evrp_tw_d import extract_root, parse_solomon_file
from safe_time_evrp.mpc3c.controllers import ControllerKind
from safe_time_evrp.mpc3c.forecast import build_anonymous_scenarios, fit_empirical_arrivals, synthetic_poisson_releases
from safe_time_evrp.mpc3c.horizon_microscope import search_horizon_causality
from safe_time_evrp.mpc3c.sim_experiment import compare_controllers, run_sim_dynamic

OUT = Path("docs/research_gate_3d")


def _seed_index(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {rec["file"]: rec for rec in payload.get("records", [])}


def _load_train_for_forecast(root: Path, splits: dict, seed_index: dict, n: int = 8):
    instances = []
    for name in splits["Cus_5"]["train"][:n]:
        rec = seed_index.get(name)
        if rec is None or not rec.get("feasible"):
            continue
        inst = parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        instances.append(inst)
    return instances


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seeds_path = Path("docs/research_gate_3c/evrptwd_seeds.json")
    payload = json.loads(seeds_path.read_text(encoding="utf-8"))
    splits = payload["splits"]
    seed_index = _seed_index(seeds_path)
    root = extract_root(Path("data/raw/evrp_tw_d"))

    train_inst = _load_train_for_forecast(root, splits, seed_index)
    arrival_model = fit_empirical_arrivals(train_inst)

    results: dict = {
        "evrptwd_dev": [],
        "evrptwd_held_out": [],
        "amazon_energy_active": [],
        "horizon_microscope": search_horizon_causality(),
        "selection_policy": "fleet_size from evrptwd_seeds.json seed-required fleet; drop if missing",
    }

    for pool_name, files in (
        ("evrptwd_dev", splits["Cus_5"]["dev"][:4]),
        ("evrptwd_held_out", splits["Cus_5"]["held_out"][:4]),
    ):
        for name in files:
            rec = seed_index.get(name)
            if rec is None or not rec.get("feasible"):
                results[pool_name].append({"file": name, "skipped": "not_in_feasible_seeds"})
                continue
            fleet = int(rec["fleet_size"])
            path = root / "anchored" / "Cus_5" / "solomon" / name
            inst = parse_solomon_file(path).with_recharge_policy("full")
            # Native Q (seed used native battery); synthetic request stream + train-fitted forecast.
            releases = synthetic_poisson_releases(
                inst,
                seed=hash(name) % 10_000,
                mean_interarrival=arrival_model.train_interarrival_mean,
            )
            forecast = build_anonymous_scenarios(
                arrival_model, n_scenarios=3, customers_per_scenario=2, seed=hash(name) % 10_000, day_horizon=200.0
            )
            report = compare_controllers(
                inst,
                fleet_size=fleet,
                horizon=12.0,
                releases=releases,
                forecast=forecast,
            )
            report["seed_fleet_size"] = fleet
            report["vehicles_used_seed"] = rec.get("vehicles_used")
            report["native_Q"] = rec.get("native_Q")
            report["file"] = name
            report["fleet_matched"] = True
            results[pool_name].append(report)

    # Amazon energy-active: small matched set.
    try:
        route_ids = list_route_ids()[:4]
    except FileNotFoundError:
        route_ids = []
    for rid in route_ids:
        inst = load_amazon_route(rid, max_customers=12, electrification=ESOGU_ENERGY_ACTIVE_V1)
        releases = [(cid, float(inst.node(cid).window.ready)) for cid in inst.customer_ids()]
        forecast = build_anonymous_scenarios(
            arrival_model, n_scenarios=2, customers_per_scenario=2, seed=7, day_horizon=12.0
        )
        report = compare_controllers(
            inst,
            fleet_size=1,
            horizon=3.0,
            releases=releases,
            forecast=forecast,
        )
        report["electrification"] = ESOGU_ENERGY_ACTIVE_V1.name
        report["file"] = rid
        report["observed_package_windows"] = inst.metadata.get("observed_package_windows")
        results["amazon_energy_active"].append(report)

    # Charge-event fraction under energy-active Amazon (single controller probe).
    charge_hits = 0
    charge_probe = []
    for rid in route_ids:
        inst = load_amazon_route(rid, max_customers=12, electrification=ESOGU_ENERGY_ACTIVE_V1)
        run = run_sim_dynamic(
            inst,
            ControllerKind.RH_OPEN_LOOP,
            fleet_size=1,
            horizon=4.0,
            releases=[(cid, float(inst.node(cid).window.ready)) for cid in inst.customer_ids()],
        )
        charge_probe.append({"route": rid, "charge_events": run.charge_events, "n_served": len(run.served)})
        if run.charge_events > 0:
            charge_hits += 1
    results["amazon_charge_probe"] = {
        "n": len(charge_probe),
        "with_charge": charge_hits,
        "fraction": (charge_hits / len(charge_probe)) if charge_probe else None,
        "detail": charge_probe,
        "config": ESOGU_ENERGY_ACTIVE_V1.name,
        "note": "consumption uplift 0.15→0.50 kWh/km at fixed 40 kWh with 12 stops; not ≤25% Q",
    }

    (OUT / "causal_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    def _agg(pool: list[dict]) -> dict:
        usable = [r for r in pool if "results" in r]
        if not usable:
            return {"n": 0}
        ctrls = list(usable[0]["results"])
        means = {
            c: sum(r["results"][c]["n_served"] for r in usable) / len(usable)
            for c in ctrls
        }
        flex_eq_roll = sum(1 for r in usable if r.get("flex_equals_rollout_sequence")) / len(usable)
        flex_neq_rh = sum(1 for r in usable if r["results"]["flexibility_mpc"]["differs_from_rh"]) / len(usable)
        charge_mean = {
            c: sum(r["results"][c]["charge_events"] for r in usable) / len(usable) for c in ctrls
        }
        return {
            "n": len(usable),
            "mean_served": means,
            "flex_equals_rollout_frac": flex_eq_roll,
            "flex_differs_rh_frac": flex_neq_rh,
            "mean_charge_events": charge_mean,
            "replay_ok_frac": sum(
                1 for r in usable if all(r["results"][c]["replay_ok"] for c in ctrls)
            )
            / len(usable),
        }

    summary = {
        "evrptwd_dev": _agg(results["evrptwd_dev"]),
        "evrptwd_held_out": _agg(results["evrptwd_held_out"]),
        "amazon_energy_active": _agg(results["amazon_energy_active"]),
        "horizon_microscope": results["horizon_microscope"],
        "amazon_charge_probe": results["amazon_charge_probe"],
    }
    (OUT / "causal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
