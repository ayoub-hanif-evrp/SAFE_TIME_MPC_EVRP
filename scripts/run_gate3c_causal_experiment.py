"""Run Gate 3C matched controller comparison on EVRP-TW-D splits + Amazon."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.data.amazon import list_route_ids, load_amazon_route
from safe_time_evrp.data.evrp_tw_d import extract_root, parse_solomon_file
from safe_time_evrp.mpc3c.experiment import compare_controllers


def main() -> None:
    root = extract_root(Path("data/raw/evrp_tw_d"))
    splits = json.loads(Path("docs/research_gate_3c/evrptwd_seeds.json").read_text(encoding="utf-8"))["splits"]
    out: dict = {"evrptwd": {"dev": [], "held_out": []}, "amazon": []}

    for part in ("dev", "held_out"):
        files = splits["Cus_5"][part][:8]
        for name in files:
            path = root / "anchored" / "Cus_5" / "solomon" / name
            if not path.exists():
                continue
            inst = parse_solomon_file(path).with_recharge_policy("full")
            # Fleet from seed summary if present; default 2.
            report = compare_controllers(inst, fleet_size=2, horizon=12.0)
            out["evrptwd"][part].append(report)

    for rid in list_route_ids()[:8]:
        inst = load_amazon_route(rid, max_customers=8)
        out["amazon"].append(compare_controllers(inst, fleet_size=1, horizon=3.0))

    dest = Path("docs/research_gate_3c/causal_results.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Aggregate divergence / service.
    def agg(rows: list[dict]) -> dict:
        n = len(rows)
        if not n:
            return {}
        keys = list(rows[0]["results"].keys())
        summary = {}
        for k in keys:
            served = [r["results"][k]["n_served"] for r in rows]
            viol = [r["results"][k]["commitment_violations"] for r in rows]
            diff = [r["results"][k]["differs_from_rh"] for r in rows]
            summary[k] = {
                "mean_served": sum(served) / n,
                "mean_violations": sum(viol) / n,
                "frac_differs_from_rh": sum(diff) / n,
            }
        flex_vs_roll = sum(
            1
            for r in rows
            if r["results"]["flexibility_mpc"]["first_action_signature"]
            != r["results"]["rollout"]["first_action_signature"]
        )
        summary["flex_vs_rollout_action_frac"] = flex_vs_roll / n
        return summary

    summary = {
        "evrptwd_dev": agg(out["evrptwd"]["dev"]),
        "evrptwd_held_out": agg(out["evrptwd"]["held_out"]),
        "amazon": agg(out["amazon"]),
    }
    Path("docs/research_gate_3c/causal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
