"""Build TW-feasible multi-vehicle seeds and freeze Gate 3C splits."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.data.evrp_tw_d import extract_root, list_solomon_files, parse_solomon_file
from safe_time_evrp.testbed.constructor import find_minimal_fleet_seed


def main() -> None:
    root = extract_root(Path("data/raw/evrp_tw_d"))
    out_dir = Path("docs/research_gate_3c")
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for scale, n_take, max_fleet in [("Cus_5", 60, 5), ("Cus_15", 40, 8)]:
        files = list_solomon_files(root, scale=scale)[:n_take]
        for path in files:
            inst = parse_solomon_file(path)
            seed = find_minimal_fleet_seed(inst, max_fleet=max_fleet, recharge_policy="full")
            records.append(
                {
                    "scale": scale,
                    "file": path.name,
                    "instance": inst.name,
                    "feasible": seed.validation.feasible,
                    "fleet_size": seed.fleet_size if seed.validation.feasible else None,
                    "vehicles_used": seed.validation.vehicles_used,
                    "distance": seed.validation.total_distance,
                    "charge_time": seed.validation.total_charge_time,
                    "reasons": seed.validation.reasons,
                    "native_Q": inst.vehicle_type.battery_capacity,
                    "n_customers": len(inst.customers),
                }
            )

    feasible = [r for r in records if r["feasible"]]
    # Deterministic splits by sorted file name within each scale among feasible seeds.
    splits: dict[str, dict[str, list[str]]] = {}
    for scale in ("Cus_5", "Cus_15"):
        names = sorted(r["file"] for r in feasible if r["scale"] == scale)
        n = len(names)
        n_train = max(1, int(0.5 * n))
        n_dev = max(1, int(0.25 * n))
        train = names[:n_train]
        dev = names[n_train : n_train + n_dev]
        held = names[n_train + n_dev :]
        splits[scale] = {"train": train, "dev": dev, "held_out": held}

    summary = {
        "n_probed": len(records),
        "n_feasible": len(feasible),
        "by_scale": {
            scale: {
                "probed": sum(1 for r in records if r["scale"] == scale),
                "feasible": sum(1 for r in records if r["scale"] == scale and r["feasible"]),
                "rate": (
                    sum(1 for r in records if r["scale"] == scale and r["feasible"])
                    / max(1, sum(1 for r in records if r["scale"] == scale))
                ),
            }
            for scale in ("Cus_5", "Cus_15")
        },
        "splits": splits,
        "records": records,
    }
    (out_dir / "evrptwd_seeds.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Gate 3C splits (EVRP-TW-D)",
        "",
        "Frozen from feasible multi-vehicle seeds under **native** battery capacity",
        "and `recharge_policy=full` (adaptive charge-to-full at stations).",
        "Geometry: `evrp_tw_d_2norm_source` (no OSM claim).",
        "",
    ]
    for scale, parts in splits.items():
        lines.append(f"## {scale}")
        lines.append("")
        for part, names in parts.items():
            lines.append(f"- **{part}** ({len(names)}):")
            for name in names:
                lines.append(f"  - `{name}`")
        lines.append("")
    rate5 = summary["by_scale"]["Cus_5"]["rate"]
    rate15 = summary["by_scale"]["Cus_15"]["rate"]
    lines.extend(
        [
            "## Feasibility rates (native Q)",
            "",
            f"- Cus_5: {summary['by_scale']['Cus_5']['feasible']}/"
            f"{summary['by_scale']['Cus_5']['probed']} = {rate5:.0%}",
            f"- Cus_15: {summary['by_scale']['Cus_15']['feasible']}/"
            f"{summary['by_scale']['Cus_15']['probed']} = {rate15:.0%}",
            "",
            "Testbed criterion (≥70% Cus_5): " + ("PASS" if rate5 >= 0.70 else "FAIL"),
            "",
        ]
    )
    (out_dir / "SPLITS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["by_scale"], indent=2))
    print("wrote", out_dir / "evrptwd_seeds.json", out_dir / "SPLITS.md")


if __name__ == "__main__":
    main()
