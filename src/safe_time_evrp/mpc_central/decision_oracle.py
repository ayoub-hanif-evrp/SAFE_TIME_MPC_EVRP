"""Small finite-horizon decision-oracle diagnostic (restricted model).

This is an enumerated first-action + scenario diagnostic — NOT a claim of global
EVRP optimality. It asks whether baseline-anchored switching can capture a
nonmyopic charge-vs-serve tradeoff that ordinary rollout or myopic B1 may miss.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.mpc3c.forecast import ForecastCustomer
from safe_time_evrp.mpc_central.causal_plant import action_to_decision
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork
from safe_time_evrp.mpc_central.paired_b1_eval import evaluate_paired_candidate
from safe_time_evrp.mpc_central.scenario_rollout import rollout_candidate
from safe_time_evrp.mpc_central.switching_mpc import (
    IMPROVEMENT_THRESHOLD,
    RISK_FLOOR,
    CommitmentViabilitySwitchingMpc,
)


@dataclass(frozen=True)
class OracleActionValue:
    action: str
    mean_value: float
    scenario_values: tuple[float, ...]
    all_replay_ok: bool


def _forecasts_from_fork_scenarios(spec) -> list[list[ForecastCustomer]]:
    out: list[list[ForecastCustomer]] = []
    for sc in spec.scenarios:
        fcs = []
        for cid, ready in sc:
            node = spec.instance.node(cid)
            fcs.append(
                ForecastCustomer(
                    customer_id=cid,
                    ready_time=ready,
                    due_time=node.window.due,
                    x=node.x,
                    y=node.y,
                    demand=node.demand,
                    service_time=node.service_time,
                    announcement_time=ready,
                )
            )
        out.append(fcs)
    return out


def run_restricted_decision_oracle(*, seed: int = 0) -> dict:
    """Enumerate Case-A charge fork first actions under fork scenarios."""
    spec = case_a_predictive_charging_fork()
    obs = spec.observation
    scenarios = _forecasts_from_fork_scenarios(spec)
    vid = obs.vehicles[0].id

    enumerated: list[OracleActionValue] = []
    for action in spec.candidate_actions:
        decision = action_to_decision(spec, action, vehicle_id=vid)
        scores = [
            rollout_candidate(
                spec.instance,
                obs,
                decision,
                fcs,
                horizon=80.0,
                max_replan_interval=5.0,
                max_events=200,
            )
            for fcs in scenarios
        ]
        ok = all(s.replay_ok for s in scores)
        vals = tuple(s.value if s.replay_ok else -1e9 for s in scores)
        mean_v = sum(vals) / len(vals) if vals else -1e9
        enumerated.append(OracleActionValue(action, mean_v, vals, ok))

    valid = [e for e in enumerated if e.all_replay_ok]
    exact_best = max(valid, key=lambda e: e.mean_value) if valid else None

    b1 = FullValidationAlnsMpc(spec.instance, 80.0, iterations=8, time_limit_seconds=0.15, seed=seed)
    b1_dec = b1.decide(obs, "oracle")
    b1_key = FirstActionKey.from_decision(b1_dec)

    # Ordinary unguarded rollout argmax among enumerated actions
    rollout_best = exact_best  # same enumeration with causal values

    # Switching rule on the two primary actions: serve_near vs charge_first
    serve = action_to_decision(spec, "serve_near", vehicle_id=vid)
    charge = action_to_decision(spec, "charge_first", vehicle_id=vid)
    public = make_public_snapshot(spec.instance, obs, 80.0).instance
    serve_ok = validate_continuation(public, obs, serve.routes, require_new=frozenset(serve.newly_accepted)).ok
    charge_ok = validate_continuation(public, obs, charge.routes, require_new=frozenset()).ok

    paired_charge = evaluate_paired_candidate(
        spec.instance,
        obs,
        "charge_first",
        charge,
        serve if serve_ok else b1_dec,  # B1-like reference: serve when feasible
        scenarios,
        horizon=80.0,
        max_replan_interval=5.0,
        max_events=200,
    )
    switch_to_charge = (
        charge_ok
        and paired_charge.mean_delta is not None
        and paired_charge.min_delta is not None
        and paired_charge.mean_delta > IMPROVEMENT_THRESHOLD
        and paired_charge.min_delta >= RISK_FLOOR
    )
    switching_action = "charge_first" if switch_to_charge else "serve_near_or_b1"

    # Live controller smoke on the observation (no episode): one decide() call.
    switch_ctrl = CommitmentViabilitySwitchingMpc(
        spec.instance,
        80.0,
        forecast=None,
        n_scenarios=len(scenarios),
        alns_iterations=8,
        time_limit_seconds=0.35,
        seed=seed,
        use_forecast=False,
        allow_switching=True,
    )
    # Inject scenarios by temporarily monkey-patching _scenario_forecasts
    switch_ctrl._scenario_forecasts = lambda _obs: scenarios  # type: ignore[method-assign]
    live = switch_ctrl.decide(obs, "oracle")
    live_key = FirstActionKey.from_decision(live)

    captures_nonmyopic = bool(
        exact_best
        and exact_best.action == "charge_first"
        and (switching_action == "charge_first" or any(leg[2] == "charge" for leg in live_key.first_legs))
    )
    merely_prefers_b1 = switching_action != "charge_first" and all(leg[2] != "charge" for leg in live_key.first_legs)

    return {
        "case_id": spec.case_id,
        "enumerated": [
            {
                "action": e.action,
                "mean_value": e.mean_value,
                "scenario_values": list(e.scenario_values),
                "all_replay_ok": e.all_replay_ok,
            }
            for e in enumerated
        ],
        "exact_restricted_best": None
        if exact_best is None
        else {"action": exact_best.action, "mean_value": exact_best.mean_value},
        "b1_first_legs": [list(x) for x in b1_key.first_legs],
        "b1_newly_accepted": list(b1_key.newly_accepted),
        "rollout_argmax": None
        if rollout_best is None
        else {"action": rollout_best.action, "mean_value": rollout_best.mean_value},
        "paired_charge_vs_serve": {
            "mean_delta": paired_charge.mean_delta,
            "min_delta": paired_charge.min_delta,
            "hoeffding_lcb": paired_charge.hoeffding_lcb,
            "commitment_ok": paired_charge.commitment_ok,
        },
        "switching_action": switching_action,
        "live_switch_first_legs": [list(x) for x in live_key.first_legs],
        "live_notes": list(live.notes)[:8],
        "captures_nonmyopic_charge": captures_nonmyopic,
        "merely_prefers_b1": merely_prefers_b1,
        "disclaimer": ("Restricted finite-horizon enumeration on Case-A fork only — not a global EVRP optimum."),
    }
