"""Run Gate 3B feasibility pilot on EVRP-TW-D Solomon instances."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.data.evrp_tw_d import (
    PILOT_BATTERY_FRACTIONS,
    extract_root,
    list_solomon_files,
    parse_solomon_file,
    summarize_extract,
    with_battery_fraction,
)
from safe_time_evrp.pilot.feasibility import pilot_contrast


def main() -> None:
    raw = Path("data/raw/evrp_tw_d")
    root = extract_root(raw)
    summary = summarize_extract(root)
    reports = []
    # Geographically/ structurally distinct via anchored Cus_5 and Cus_15, first N files.
    for scale, n_take in [("Cus_5", 20), ("Cus_15", 10)]:
        files = list_solomon_files(root, scale=scale)[:n_take]
        for path in files:
            base = parse_solomon_file(path)
            for frac in PILOT_BATTERY_FRACTIONS:
                inst = with_battery_fraction(base, frac, f"f{frac}")
                report = pilot_contrast(inst)
                report.update(
                    {
                        "scale": scale,
                        "file": path.name,
                        "battery_fraction": frac,
                        "native_Q": base.vehicle_type.battery_capacity,
                        "native_r": base.vehicle_type.consumption_rate,
                        "distance_definition": next(iter(inst.arcs.values())).distance_definition,
                    }
                )
                reports.append(report)

    out = Path("docs/research_gate_3b/pilot_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"extract_summary": summary, "n_reports": len(reports), "reports": reports}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Aggregate
    by_frac: dict[float, list] = {}
    for r in reports:
        by_frac.setdefault(r["battery_fraction"], []).append(r)
    print("extract", summary)
    for frac, rows in sorted(by_frac.items()):
        energy_bind = sum(1 for r in rows if r["energy_exceeds_Q"])
        energy_fail = sum(1 for r in rows if not r["nn_energy_only_feasible"])
        energy_rescue = sum(1 for r in rows if r["battery_changes_energy_decision"])
        tw_fail = sum(1 for r in rows if not r["nn_full_feasible"])
        print(
            f"frac={frac}: n={len(rows)} energy>Q={energy_bind} energy_fail={energy_fail} "
            f"charge_rescues_energy={energy_rescue} full_tw_fail={tw_fail} "
            f"rate_energy_bind={energy_bind / len(rows):.2f} "
            f"rate_energy_rescue={energy_rescue / len(rows):.2f}"
        )
    print("wrote", out)


if __name__ == "__main__":
    main()
