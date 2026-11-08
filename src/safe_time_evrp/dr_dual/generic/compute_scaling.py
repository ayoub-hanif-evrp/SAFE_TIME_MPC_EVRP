"""Decisive computational study on frozen generic instances."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from time import perf_counter

from safe_time_evrp.dr_dual.generic.discriminating_suite import build_discriminating_suite
from safe_time_evrp.dr_dual.generic.exact_dp import solve_generic_exact
from safe_time_evrp.dr_dual.generic.model import initial_generic_state
from safe_time_evrp.dr_dual.generic.policy_class import RESTRICTED_CONTINUATION_MAX_LEN
from safe_time_evrp.dr_dual.solver import (
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_passive_mpc,
    solve_robust_mpc,
)


def run_scaling_study(*, trials: int = 3) -> dict:
    suite = build_discriminating_suite()
    rows = []
    for inst in suite:
        net = inst.net
        state = initial_generic_state(net)
        exact = solve_generic_exact(net, max_len=RESTRICTED_CONTINUATION_MAX_LEN)
        modes = {
            "unpruned": (False, "clairvoyant"),
            "clairvoyant": (True, "clairvoyant"),
            "generic": (True, "generic"),
            "combined": (True, "combined"),
        }
        mode_stats = {}
        for name, (use_p, bmode) in modes.items():
            times = []
            last = None
            for _ in range(trials):
                t0 = perf_counter()
                last = solve_dr_dual(net, state=state, use_pruning=use_p, bound_mode=bmode)
                times.append(perf_counter() - t0)
            assert last is not None
            mode_stats[name] = {
                "first": last.selected_action,
                "value": last.selected_value,
                "expanded": last.actions_expanded,
                "pruned": last.actions_pruned_by_bound,
                "heavy": last.counters.get("total_heavy_calls"),
                "mean_s": sum(times) / len(times),
                "agrees_exact": last.selected_action == exact.first_action_key,
                "notes": last.notes[:6],
            }
        u = mode_stats["unpruned"]
        for name in ("clairvoyant", "generic", "combined"):
            m = mode_stats[name]
            m["heavy_improved"] = (m["heavy"] or 0) < (u["heavy"] or 0) and (m["pruned"] or 0) > 0
            m["time_improved"] = m["mean_s"] + 1e-12 < u["mean_s"]
            if u["mean_s"] > 1e-9:
                m["time_reduction_frac"] = (u["mean_s"] - m["mean_s"]) / u["mean_s"]
            else:
                m["time_reduction_frac"] = 0.0

        rows.append(
            {
                "instance_id": inst.instance_id,
                "tags": list(inst.tags),
                "expected_traits": list(getattr(inst, "expected_traits", ())),
                "exact_first": exact.first_action_key,
                "exact_value": exact.value,
                "exact_status": exact.status.value,
                "baselines": {
                    "robust": solve_robust_mpc(net, state=state).selected_action,
                    "passive": solve_passive_mpc(net, state=state).selected_action,
                    "info_gain": solve_info_gain_heuristic(net, state=state).selected_action,
                },
                "modes": mode_stats,
            }
        )

    # Aggregate
    n = len(rows)
    gen_agree = sum(1 for r in rows if r["modes"]["generic"]["agrees_exact"])
    gen_heavy = sum(1 for r in rows if r["modes"]["generic"]["heavy_improved"])
    gen_time = sum(1 for r in rows if r["modes"]["generic"]["time_improved"])
    reductions = [r["modes"]["generic"]["time_reduction_frac"] for r in rows]
    return {
        "rows": rows,
        "summary": {
            "n_instances": n,
            "generic_agrees_exact": gen_agree,
            "generic_heavy_ops_improved": gen_heavy,
            "generic_wall_time_improved": gen_time,
            "generic_median_time_reduction_frac": median(reductions) if reductions else None,
            "screening_target_20_30_pct": (median(reductions) >= 0.20 if reductions else False),
            "note": "Screening target is research criterion, not publication guarantee",
        },
    }


def write_scaling_artifacts(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_scaling_study(trials=3)
    (out_dir / "computational_scaling.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_scaling_artifacts(Path("docs/decision_relevant_dual_mpc"))
    print(json.dumps(art["summary"], indent=2))
