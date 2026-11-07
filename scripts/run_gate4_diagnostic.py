"""Gate 4 matched diagnostic with preregistered announcements (exploratory only).

Does NOT search mu scales to create a preferred controller gap.
Writes manifests tied to the generating source commit (immutable).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from safe_time_evrp.data.amazon import list_route_ids, load_amazon_route
from safe_time_evrp.data.evrp_tw_d import extract_root, parse_solomon_file
from safe_time_evrp.mpc3c.announcement import GATE4_DEV_ANNOUNCEMENT_SPECS
from safe_time_evrp.mpc3c.commitment_oracle import investigate_commitment_cost_candidates
from safe_time_evrp.mpc3c.controllers import CONTROLLER_LABELS, ControllerKind
from safe_time_evrp.mpc3c.forecast import build_anonymous_scenarios, fit_empirical_arrivals, forecast_seed_for
from safe_time_evrp.mpc3c.offline_reference import offline_service_reference
from safe_time_evrp.mpc3c.seeds import instance_content_hash
from safe_time_evrp.mpc3c.sim_experiment import TimingContract, compare_controllers, run_sim_dynamic

OUT = Path("docs/research_gate_4")


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_commit = _git_head()
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
    spatial_model = fit_empirical_arrivals(train_inst)
    day_horizon = max(
        (float(n.window.due) for inst in train_inst for n in inst.customers),
        default=200.0,
    )

    rows = []
    for name in splits["Cus_5"]["dev"][:8]:
        rec = seed_index.get(name)
        if not rec or not rec.get("feasible"):
            continue
        fleet = int(rec["fleet_size"])
        inst = parse_solomon_file(root / "anchored" / "Cus_5" / "solomon" / name).with_recharge_policy("full")
        for spec in GATE4_DEV_ANNOUNCEMENT_SPECS:
            releases = spec.materialize(inst, seed_key=f"{name}|{spec.spec_id}")
            ref = offline_service_reference(
                inst, releases, fleet_size=fleet, try_exact=len(inst.customer_ids()) <= 5
            )
            forecast = build_anonymous_scenarios(
                spatial_model,
                n_scenarios=1,
                customers_per_scenario=2,
                seed=forecast_seed_for(f"{name}|{spec.spec_id}"),
                day_horizon=day_horizon,
            )
            report = compare_controllers(
                inst,
                fleet_size=fleet,
                horizon=12.0,
                releases=releases,
                forecast=forecast,
            )
            reactive = run_sim_dynamic(
                inst,
                ControllerKind.REACTIVE,
                fleet_size=fleet,
                horizon=12.0,
                releases=releases,
                forecast=forecast,
                timing_contract=TimingContract.INSTANTANEOUS,
            )
            rh = run_sim_dynamic(
                inst,
                ControllerKind.RH_OPEN_LOOP,
                fleet_size=fleet,
                horizon=12.0,
                releases=releases,
                forecast=forecast,
                timing_contract=TimingContract.INSTANTANEOUS,
            )
            rows.append(
                {
                    "instance": name,
                    "instance_hash": instance_content_hash(inst),
                    "announcement_spec_id": spec.spec_id,
                    "mean_interarrival": spec.mean_interarrival,
                    "fleet_size": fleet,
                    "offline_ref": {
                        "feasible_lower_bound": ref.feasible_lower_bound,
                        "certified_upper_bound": ref.certified_upper_bound,
                        "exact_optimum": ref.exact_optimum,
                        "bound_kind": ref.bound_kind.value,
                        "service_rate_lb": ref.service_rate_lb,
                        "n_window_impossible": ref.n_window_impossible,
                    },
                    "n_served": {k: v["n_served"] for k, v in report["results"].items()},
                    "service_rate": {k: v["service_rate"] for k, v in report["results"].items()},
                    "reactive_n_served": len(reactive.served),
                    "rh_n_served": len(rh.served),
                    "rh_minus_reactive": len(rh.served) - len(reactive.served),
                    "flex_equals_rollout_sequence": report.get("flex_equals_rollout_sequence"),
                    "exploratory_only": True,
                }
            )

    amazon_rows = []
    try:
        for rid in list_route_ids()[:2]:
            inst = load_amazon_route(rid, max_customers=8)
            releases = [(cid, float(inst.node(cid).window.ready)) for cid in inst.customer_ids()]
            report = compare_controllers(inst, fleet_size=1, horizon=3.0, releases=releases)
            amazon_rows.append(
                {
                    "route_id": rid,
                    "n_served": {k: v["n_served"] for k, v in report["results"].items()},
                    "exploratory_only": True,
                }
            )
    except FileNotFoundError:
        amazon_rows.append({"note": "amazon_data_absent"})

    theory = investigate_commitment_cost_candidates()
    diagnostic = {
        "gate": "4",
        "source_commit": source_commit,
        "controller_labels": {k.value: v for k, v in CONTROLLER_LABELS.items()},
        "note": (
            "Exploratory diagnostic with preregistered announcement specs. "
            "Not an independent evaluation sample. Constructive offline rates are "
            "FEASIBLE_LOWER_BOUNDs, not upper bounds. Gate 3F middle-regime search preserved "
            "as exploratory evidence only."
        ),
        "evrp_tw_d": rows,
        "amazon": amazon_rows,
        "commitment_cost_theory": theory,
    }
    mean_gap = sum(r["rh_minus_reactive"] for r in rows) / len(rows) if rows else None
    summary = {
        "gate": "4",
        "source_commit": source_commit,
        "n_evrp_rows": len(rows),
        "mean_rh_minus_reactive": mean_gap,
        "theory_stop": theory["theory_stop"],
        "recommendation": theory["recommendation"],
        "artifact_policy": "source_commit_is_generating_revision_not_self_hash",
    }
    (OUT / "matched_diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    (OUT / "matched_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
