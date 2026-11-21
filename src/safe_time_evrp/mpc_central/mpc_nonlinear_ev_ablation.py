"""Campaign B: nonlinear vs linear-charge planning on predeclared tight-EV cells.

Plant / replay always use nonlinear piecewise charging. Ablation swaps only the
MPC planner energy model to linear g*(target-soc). Claim is local: where linear
understates charge time, nonlinear keeps commitments / service.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    build_dynamic_episode_v2,
    environment_seed_for,
    policy_seed_for,
)
from safe_time_evrp.data.evrp_tw_d import (
    extract_root,
    list_solomon_files,
    parse_solomon_file,
    with_battery_fraction,
)
from safe_time_evrp.data.paths import evrp_tw_d_dir
from safe_time_evrp.environment.energy import LinearChargeEnergy, NonlinearPiecewiseChargeEnergy
from safe_time_evrp.models.instance import Instance, NodeKind, VehicleType
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.validation.replay import validate_log

ALNS_ITER = 8
BUDGET = 0.35
N_REAL = 1
BATTERY_FRACTION = 0.25
CHARGER_KEEP = 1
PLANT = NonlinearPiecewiseChargeEnergy()
ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "experiments" / "MPC_NONLINEAR_EV_ABLATION.json"
OUT_MD = ROOT / "docs" / "experiments" / "MPC_NONLINEAR_EV_ABLATION.md"


def _scale_battery(inst: Instance, fraction: float) -> Instance:
    vt = inst.vehicle_type
    vehicle = VehicleType(
        battery_capacity=vt.battery_capacity * fraction,
        load_capacity=vt.load_capacity,
        consumption_rate=vt.consumption_rate,
        inverse_recharge_rate=vt.inverse_recharge_rate,
        velocity=vt.velocity,
        recharge_policy=vt.recharge_policy,
    )
    return Instance(
        name=f"{inst.name}|bat={fraction}",
        nodes=inst.nodes,
        arcs=inst.arcs,
        vehicle_type=vehicle,
        depot_id=inst.depot_id,
        source_format=inst.source_format,
        source_name=inst.source_name,
        assumptions=inst.assumptions + (f"battery_fraction={fraction}",),
        station_capacity=inst.station_capacity,
        metadata={**inst.metadata, "tight_ev": "1"},
    )


def _sparse_chargers(inst: Instance, keep: int) -> Instance:
    chargers = sorted(inst.chargers, key=lambda n: n.id)
    if keep >= len(chargers):
        return inst
    keep_ids = {c.id for c in chargers[:keep]}
    nodes = {
        nid: n
        for nid, n in inst.nodes.items()
        if n.kind is not NodeKind.CHARGER or nid in keep_ids
    }
    arcs = {
        k: v
        for k, v in inst.arcs.items()
        if k[0] in nodes and k[1] in nodes
    }
    return Instance(
        name=f"{inst.name}|chg={keep}",
        nodes=nodes,
        arcs=arcs,
        vehicle_type=inst.vehicle_type,
        depot_id=inst.depot_id,
        source_format=inst.source_format,
        source_name=inst.source_name,
        assumptions=inst.assumptions + (f"charger_keep={keep}",),
        station_capacity=inst.station_capacity,
        metadata={**inst.metadata, "sparse_chargers": str(keep)},
    )


def _force_partial(inst: Instance) -> Instance:
    """Partial recharge so mid/high-SoC segments expose linear vs nonlinear time."""
    return inst.with_recharge_policy("partial")


def _tighten(inst: Instance) -> Instance:
    return _force_partial(_sparse_chargers(_scale_battery(inst, BATTERY_FRACTION), CHARGER_KEEP))


def _mechanism_charge_mismatch_demo() -> dict:
    """Deterministic Montoya demo: linear certifies a near-full top-up that nonlinear rejects.

    Vehicle is already at the charger with high SoC; a tight TW customer requires a
    partial top-up. Linear g*Δsoc understates duration → Validate OK; nonlinear → not OK.
    """
    from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
    from safe_time_evrp.models.instance import Node, TimeWindow, build_euclidean_instance
    from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit

    q = 20.0
    vehicle = VehicleType(q, 20.0, 1.0, 1.0, 1.0, "partial")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 300), 0),
        Node("S0", NodeKind.CHARGER, 5, 0, 0, TimeWindow(0, 300), 0),
        # Already at S0 with goods; top-up near full then S0→C1=5. Due splits models.
        Node("C1", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 7.5), 2),
    ]
    inst = build_euclidean_instance(
        "mechanism_near_full_charge",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="nonlinear_ev_ablation",
        assumptions=("montoya_mechanism", "near_full_partial_charge"),
    )
    # Near-full top-up where concave curve is slower than g*Δsoc (85%→95%).
    soc0 = 17.0
    target = 19.0
    t0 = 0.0
    demand = float(inst.node("C1").demand)
    anchor = Anchor(node="S0", time=t0, soc=soc0, load=demand, onboard=frozenset({"C1"}))
    view = VehicleView("v0", "idle", "S0", soc0, demand, ("C1",), anchor, None)
    obs = Observation(t0, (view,), (), ("C1",), (), (), (), (), public_customer_count=1)
    routes = {
        "v0": [
            Visit("S0", "charge", charge_target=target),
            Visit("C1", "service"),
            Visit("D0", "return"),
        ]
    }
    lin = validate_continuation(inst, obs, routes, energy=LinearChargeEnergy())
    nl = validate_continuation(inst, obs, routes, energy=NonlinearPiecewiseChargeEnergy())
    lin_t = LinearChargeEnergy().charge_duration(soc0, target, 1.0, battery_capacity=q)
    nl_t = NonlinearPiecewiseChargeEnergy().charge_duration(soc0, target, 1.0, battery_capacity=q)
    return {
        "name": "near_full_partial_topup_then_tight_tw",
        "soc_before": soc0,
        "charge_target": target,
        "battery_capacity": q,
        "linear_charge_seconds": lin_t,
        "nonlinear_charge_seconds": nl_t,
        "linear_validate_ok": lin.ok,
        "nonlinear_validate_ok": nl.ok,
        "linear_reasons": list(lin.reasons),
        "nonlinear_reasons": list(nl.reasons),
        "mechanism_holds": bool(lin.ok and not nl.ok),
        "interpretation": (
            "Linear planning certifies a route nonlinear physics rejects (or vice versa only "
            "if windows allow). Claim support when linear_ok and not nonlinear_ok."
        ),
    }


def _synthetic_montoya_cell() -> dict:
    """Predeclared mechanism cell: near-full partial charge under concave curve.

    Linear planner understates charge duration; nonlinear plant consumes more time.
    """
    from safe_time_evrp.models.instance import Node, TimeWindow, build_euclidean_instance

    # Small Q; long legs; must top up near full pack before last customer.
    vehicle = VehicleType(20.0, 20.0, 1.0, 1.0, 1.0, "partial")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 4, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 8, 0, 1, TimeWindow(0, 40), 2),
        Node("C2", NodeKind.CUSTOMER, 14, 0, 1, TimeWindow(50, 120), 2),
        Node("C3", NodeKind.CUSTOMER, 4, 6, 1, TimeWindow(80, 160), 2),
    ]
    inst = build_euclidean_instance(
        "synthetic_montoya_tight_ev",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="nonlinear_ev_ablation",
        assumptions=("tight_ev", "partial_near_full_charge"),
    )
    releases = [("C1", 0.0), ("C2", 0.0), ("C3", 15.0)]
    case = BaselineCase(
        case_id="synthetic_montoya_tight_ev",
        instance=inst,
        releases=releases,
        fleet_size=1,
        horizon=200.0,
        max_replan_interval=20.0,
        t_max=200.0,
        tags=("synthetic", "tight_ev", "montoya_mechanism"),
    )
    return {"dataset": "synthetic", "stem": "synthetic_montoya", "realization": 0, "case": case, "pol": 3}


def _summarize(case, name, result, ctrl, wall, failure=None):
    if failure:
        return {
            "controller": name,
            "failure": failure,
            "replay_ok": False,
            "completed_count": None,
            "accepted_unfulfilled_count": None,
            "economic_objective": None,
            "charge_events": None,
            "wall_seconds": wall,
        }
    rep = validate_log(case.instance, result.log)
    final = result.final_requests
    completed = sum(1 for st in final.values() if st == "completed")
    au = sum(1 for st in final.values() if st == "accepted_unfulfilled")
    dist = executed_distance_from_log(case.instance, result.log) or 0.0
    charge_events = sum(1 for rec in result.log if rec.kind == "charge_start")
    soc_fail = 0
    if not rep.ok and rep.code in {"impossible_charge", "travel_energy", "soc"}:
        soc_fail = 1
    # Soft SoC stress: AU or incomplete under tight battery.
    econ = 100.0 * completed - 250.0 * au - dist
    return {
        "controller": name,
        "failure": None if rep.ok else f"replay:{rep.code}",
        "replay_ok": rep.ok,
        "soc_or_charge_replay_fail": soc_fail,
        "completed_count": completed,
        "accepted_unfulfilled_count": au,
        "executed_distance": dist,
        "economic_objective": econ,
        "charge_events": charge_events,
        "wall_seconds": wall,
        "fallback_count": result.fallback_count,
        "loss_events": list(getattr(getattr(ctrl, "profile", None), "loss_events", []) or []),
    }


def _ctrl(inst, *, pol: int, linear: bool):
    energy = LinearChargeEnergy() if linear else NonlinearPiecewiseChargeEnergy()
    return CommitmentSafeStochasticMpc(
        inst,
        horizon=max(float(inst.node(inst.depot_id).window.due), 1.0),
        use_forecast=False,
        n_scenarios=1,
        require_terminal_commitment=True,
        spi_mode=True,
        spi_advantage_margin=0.0,
        alns_iterations=ALNS_ITER,
        time_limit_seconds=BUDGET,
        seed=pol,
        energy=energy,
    )


def _run(case: BaselineCase, name: str, *, linear: bool, pol: int):
    t0 = time.perf_counter()
    ctrl = _ctrl(case.instance, pol=pol, linear=linear)
    try:
        result = run_episode(
            case.instance,
            case.releases,
            fleet_size=case.fleet_size,
            horizon=case.horizon,
            max_replan_interval=case.max_replan_interval,
            t_max=case.t_max,
            controller=ctrl,
            energy=PLANT,  # plant always nonlinear
        )
        return _summarize(case, name, result, ctrl, time.perf_counter() - t0)
    except Exception as exc:  # noqa: BLE001
        return _summarize(
            case, name, None, ctrl, time.perf_counter() - t0, failure=f"{type(exc).__name__}:{exc}"
        )


def _schneider_cells():
    splits = stratified_split_small()
    stems = sorted(splits["development"], key=lambda s: (0 if "C5" in s else 1 if "C10" in s else 2, s))
    # Predeclared tight subset: first 3 C5/C10-ish stems.
    stems = [s for s in stems if "C100" not in s][:3]
    cells = []
    for stem in stems:
        for ridx in range(N_REAL):
            env = environment_seed_for(stem, ridx) & 0x7FFFFFFF
            pol = policy_seed_for(stem, ridx, "shared")
            episode, _, _ = build_dynamic_episode_v2(
                stem, environment_seed=env, policy_seed=pol, dynamicity="medium", split="development"
            )
            case = episode.case
            tight = _tighten(case.instance)
            case = BaselineCase(
                case_id=f"{case.case_id}|tight_ev",
                instance=tight,
                releases=list(case.releases),
                fleet_size=case.fleet_size,
                horizon=case.horizon,
                max_replan_interval=case.max_replan_interval,
                t_max=case.t_max,
                tags=tuple(case.tags) + ("tight_ev", f"bat={BATTERY_FRACTION}", f"chg={CHARGER_KEEP}"),
            )
            cells.append({"dataset": "schneider", "stem": stem, "realization": ridx, "case": case, "pol": pol})
    return cells


def _evrp_tw_d_cells():
    root = extract_root(evrp_tw_d_dir())
    cells = []
    for scale in ("Cus_5", "Cus_15"):
        files = list_solomon_files(root, scale=scale)[:2]
        for path in files:
            inst = _tighten(with_battery_fraction(parse_solomon_file(path), 1.0, "native"))
            # Battery already scaled in _tighten; with_battery_fraction(1.0) is identity label.
            cust = inst.customer_ids()
            # Simple dynamic releases: 30% known at 0, rest staggered.
            n_known = max(1, int(0.3 * len(cust)))
            releases = []
            for i, cid in enumerate(cust):
                t = 0.0 if i < n_known else 5.0 * (i - n_known + 1)
                releases.append((cid, t))
            depot_due = float(inst.node(inst.depot_id).window.due)
            horizon = depot_due
            case = BaselineCase(
                case_id=f"evrp_tw_d|{scale}|{path.stem}|tight_ev",
                instance=inst,
                releases=releases,
                fleet_size=1 if scale == "Cus_5" else 2,
                horizon=horizon,
                max_replan_interval=max(5.0, horizon / 40.0),
                t_max=horizon,
                tags=("evrp_tw_d", scale, "tight_ev"),
            )
            cells.append(
                {
                    "dataset": "evrp_tw_d",
                    "stem": f"{scale}/{path.stem}",
                    "realization": 0,
                    "case": case,
                    "pol": 7,
                }
            )
    return cells


def _mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None}
    return {"n": len(xs), "mean": sum(xs) / len(xs), "median": statistics.median(xs)}


def run_ablation() -> dict:
    cells = [_synthetic_montoya_cell()] + _schneider_cells() + _evrp_tw_d_cells()
    rows = []
    for cell in cells:
        case = cell["case"]
        row = {
            "dataset": cell["dataset"],
            "stem": cell["stem"],
            "realization": cell["realization"],
            "battery_fraction": BATTERY_FRACTION,
            "charger_keep": CHARGER_KEEP,
            "controllers": {
                "css_spi_nonlinear": _run(case, "css_spi_nonlinear", linear=False, pol=cell["pol"]),
                "css_spi_linear_plan": _run(case, "css_spi_linear_plan", linear=True, pol=cell["pol"]),
            },
        }
        rows.append(row)

    def rollup(name):
        keys = (
            "economic_objective",
            "completed_count",
            "accepted_unfulfilled_count",
            "charge_events",
            "soc_or_charge_replay_fail",
        )
        buckets = {k: [] for k in keys}
        replay_fail = 0
        hard_fail = 0
        for row in rows:
            c = row["controllers"][name]
            if c.get("failure") and not str(c.get("failure", "")).startswith("replay:"):
                hard_fail += 1
            if c.get("replay_ok") is False:
                replay_fail += 1
            for k in keys:
                buckets[k].append(c.get(k))
        return {
            **{k: _mean(v) for k, v in buckets.items()},
            "replay_failures": replay_fail,
            "hard_failures": hard_fail,
            "n_cells": len(rows),
        }

    paired = []
    for row in rows:
        a = row["controllers"]["css_spi_nonlinear"]
        b = row["controllers"]["css_spi_linear_plan"]
        if a.get("economic_objective") is None or b.get("economic_objective") is None:
            continue
        paired.append(
            {
                "stem": row["stem"],
                "dataset": row["dataset"],
                "delta_j": a["economic_objective"] - b["economic_objective"],
                "delta_completed": (a["completed_count"] or 0) - (b["completed_count"] or 0),
                "delta_au": (a["accepted_unfulfilled_count"] or 0) - (b["accepted_unfulfilled_count"] or 0),
                "linear_replay_fail": not b.get("replay_ok"),
                "nonlinear_replay_fail": not a.get("replay_ok"),
            }
        )
    dj = [p["delta_j"] for p in paired]
    claim_cells = [
        p
        for p in paired
        if p["delta_j"] > 0
        or p["delta_completed"] > 0
        or p["delta_au"] < 0
        or (p["linear_replay_fail"] and not p["nonlinear_replay_fail"])
    ]
    # Predeclared physical gap (Montoya): same ΔE near full is slower under nonlinear.
    q, g, soc, tgt = 100.0, 1.0, 85.0, 95.0
    nl_t = NonlinearPiecewiseChargeEnergy().charge_duration(soc, tgt, g, battery_capacity=q)
    lin_t = LinearChargeEnergy().charge_duration(soc, tgt, g, battery_capacity=q)
    physical_gap = {
        "soc_from": soc,
        "soc_to": tgt,
        "battery_capacity": q,
        "nonlinear_seconds": nl_t,
        "linear_seconds": lin_t,
        "linear_understates_by": nl_t - lin_t,
        "relative_understatement": (nl_t - lin_t) / nl_t if nl_t else None,
    }
    mechanism = _mechanism_charge_mismatch_demo()

    payload = {
        "protocol": "mpc_nonlinear_ev_ablation_v1",
        "plant": "nonlinear_piecewise_charge",
        "ablation": "linear_g_delta_soc_planning_only",
        "battery_fraction": BATTERY_FRACTION,
        "charger_keep": CHARGER_KEEP,
        "partial_recharge_policy": True,
        "n_cells": len(rows),
        "physical_charge_gap_near_full": physical_gap,
        "mechanism_demo": mechanism,
        "summary": {
            "css_spi_nonlinear": rollup("css_spi_nonlinear"),
            "css_spi_linear_plan": rollup("css_spi_linear_plan"),
        },
        "paired_nonlinear_minus_linear": {
            "n": len(paired),
            "delta_j": _mean(dj),
            "frac_nonlinear_better_j": (sum(1 for d in dj if d > 0) / len(dj)) if dj else None,
            "claim_support_cells": len(claim_cells),
            "per_cell": paired,
        },
        "rows": rows,
        "claim_scope": (
            "Local to predeclared tight-EV cells + physical near-full charge gap: nonlinear "
            "is necessary when linear planning understates charge time. Not a global J brag. "
            "Null closed-loop deltas are reported honestly when both planners emit the same acts."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_md(payload)
    return payload


def _write_md(payload: dict) -> None:
    s = payload["summary"]
    p = payload["paired_nonlinear_minus_linear"]
    lines = [
        "# MPC nonlinear EV ablation (Campaign B)",
        "",
        f"- Protocol: `{payload['protocol']}`",
        f"- Plant: `{payload['plant']}`; ablation planner: `{payload['ablation']}`",
        (
            f"- Tight-EV: battery×{payload['battery_fraction']}, "
            f"keep {payload['charger_keep']} charger(s), partial recharge"
        ),
        f"- Cells: {payload['n_cells']}",
        "",
        "## Physical near-full charge gap",
        "",
        f"- {payload['physical_charge_gap_near_full']}",
        "",
        "## Mechanism demo (Validate under linear vs nonlinear)",
        "",
        f"- mechanism_holds={payload['mechanism_demo'].get('mechanism_holds')}",
        f"- linear_ok={payload['mechanism_demo'].get('linear_validate_ok')} "
        f"nonlinear_ok={payload['mechanism_demo'].get('nonlinear_validate_ok')}",
        f"- charge times: linear={payload['mechanism_demo'].get('linear_charge_seconds')}, "
        f"nonlinear={payload['mechanism_demo'].get('nonlinear_charge_seconds')}",
        "",
        "## Closed-loop summary (honest; may be null if no charge acts)",
        "",
        f"- Nonlinear mean J: {s['css_spi_nonlinear']['economic_objective'].get('mean')}",
        f"- Linear-plan mean J: {s['css_spi_linear_plan']['economic_objective'].get('mean')}",
        f"- Mean ΔJ (NL−linear): {p['delta_j'].get('mean')}",
        f"- Frac NL better J: {p['frac_nonlinear_better_j']}",
        f"- Claim-support cells: {p['claim_support_cells']} / {p['n']}",
        f"- Linear replay failures: {s['css_spi_linear_plan']['replay_failures']}",
        f"- Nonlinear replay failures: {s['css_spi_nonlinear']['replay_failures']}",
        "",
        "## Claim scope",
        "",
        payload["claim_scope"],
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    out = run_ablation()
    print(
        json.dumps(
            {
                "n_cells": out["n_cells"],
                "mechanism_demo": out["mechanism_demo"],
                "physical_charge_gap_near_full": out["physical_charge_gap_near_full"],
                "paired": out["paired_nonlinear_minus_linear"],
                "summary": out["summary"],
            },
            indent=2,
        )
    )
