"""Exact tiny first-action evaluator for MPC causality gates.

Policies compared on the *same* candidate first-action set:
- reactive: score using the no-future scenario only (forecast-blind)
- stochastic_rollout: expected causal recourse value over scenarios
- commitment_safe_mpc: same predictive objective among actions with a feasible
  nominal first-action prefix (Phase-3 stand-in; no claim of novelty vs rollout)
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route, tour_customer_ids
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit
from safe_time_evrp.mpc_central.forks import ForkSpec

SERVICE_REWARD = 100.0
DISTANCE_PENALTY = 1.0
CHARGE_PENALTY = 0.1


@dataclass(frozen=True)
class PrefixResult:
    feasible: bool
    reason: str
    anchor: Anchor
    served: tuple[str, ...]
    distance: float
    charge_time: float


@dataclass(frozen=True)
class ActionScore:
    action: str
    reactive_value: float
    stochastic_value: float
    safe: bool
    per_scenario: tuple[float, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PolicyChoice:
    reactive: str
    stochastic_rollout: str
    commitment_safe_mpc: str
    reactive_equals_stochastic: bool
    mpc_equals_stochastic: bool
    scores: tuple[ActionScore, ...]


def simulate_prefix(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    energy: NominalLinearEnergy | None = None,
) -> PrefixResult:
    """Simulate a visit prefix **without** forcing a depot return."""
    model = energy or NominalLinearEnergy()
    vehicle = instance.vehicle_type
    depot = instance.depot_id
    node = anchor.node
    time = anchor.time
    soc = anchor.soc
    load = anchor.load
    onboard = set(anchor.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []

    def load_customers(ids: list[str]) -> str | None:
        nonlocal load
        extra = 0.0
        for cid in ids:
            if cid in onboard:
                continue
            cust = instance.node(cid)
            if cust.kind is not NodeKind.CUSTOMER:
                return "service_target_not_customer"
            extra += cust.demand
        if load + extra > vehicle.load_capacity + EPS:
            return "excess_payload"
        for cid in ids:
            if cid not in onboard:
                onboard.add(cid)
                load += instance.node(cid).demand
        return None

    if node == depot:
        initial = [cid for cid in tour_customer_ids(visits, 0) if cid not in onboard]
        problem = load_customers(initial)
        if problem:
            return PrefixResult(False, problem, anchor, (), 0.0, 0.0)

    for index, visit in enumerate(visits):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return PrefixResult(False, f"missing_arc:{node}->{visit.node_id}", anchor, (), 0.0, 0.0)
            used = model.travel_energy(instance, arc, soc=soc, load=load)
            if soc - used < -EPS:
                return PrefixResult(False, "battery_depleted", anchor, (), 0.0, 0.0)
            soc -= used
            if soc < 0 and soc >= -EPS:
                soc = 0.0
            time += arc.travel_time
            distance += arc.distance
            node = visit.node_id

        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                return PrefixResult(False, "service_target_not_customer", anchor, (), 0.0, 0.0)
            if visit.node_id not in onboard:
                return PrefixResult(False, "goods_not_onboard", anchor, (), 0.0, 0.0)
            if time > cust.window.due + EPS:
                return PrefixResult(False, "missed_window", anchor, (), 0.0, 0.0)
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            onboard.discard(visit.node_id)
            served.append(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if station.kind is not NodeKind.CHARGER:
                return PrefixResult(False, "charge_away_from_station", anchor, (), 0.0, 0.0)
            if time > station.window.due + EPS:
                return PrefixResult(False, "charger_window", anchor, (), 0.0, 0.0)
            if time < station.window.ready:
                time = station.window.ready
            target = vehicle.battery_capacity
            duration = model.charge_duration(soc, target, vehicle.inverse_recharge_rate)
            time += duration
            charge_time += duration
            soc = target
        elif visit.purpose == "reload":
            if node != depot:
                return PrefixResult(False, "reload_away_from_depot", anchor, (), 0.0, 0.0)
            load = 0.0
            onboard.clear()
            problem = load_customers(tour_customer_ids(visits, index + 1))
            if problem:
                return PrefixResult(False, problem, anchor, (), 0.0, 0.0)
        else:
            return PrefixResult(False, f"unsupported_purpose:{visit.purpose}", anchor, (), 0.0, 0.0)

    new_anchor = Anchor(node, time, soc, load, frozenset(onboard))
    return PrefixResult(True, "ok", new_anchor, tuple(served), distance, charge_time)


def _route_value(result) -> float:
    if not result.feasible:
        return -1e9
    return (
        SERVICE_REWARD * len(result.served) - DISTANCE_PENALTY * result.distance - CHARGE_PENALTY * result.charge_time
    )


def _best_suffix_value(
    instance: Instance,
    anchor: Anchor,
    *,
    must_serve: tuple[str, ...],
    optional: tuple[str, ...],
    energy: NominalLinearEnergy,
) -> float:
    best = -1e9
    opts = list(optional)
    n = len(opts)
    for mask in range(1 << n):
        chosen = [opts[i] for i in range(n) if mask & (1 << i)]
        customers = list(must_serve) + chosen
        skeletons: list[list[Visit]] = [[Visit(c, "service") for c in customers]]
        if "S" in instance.nodes:
            skeletons.append([Visit("S", "charge"), *[Visit(c, "service") for c in customers]])
            if len(customers) >= 2:
                skeletons.append(
                    [
                        Visit(customers[0], "service"),
                        Visit("S", "charge"),
                        *[Visit(c, "service") for c in customers[1:]],
                    ]
                )
            if len(customers) >= 1:
                skeletons.append([Visit(customers[0], "service"), Visit("S", "charge")])
                skeletons.append(
                    [Visit("S", "charge"), Visit(customers[0], "service"), Visit("S", "charge")]
                    + [Visit(c, "service") for c in customers[1:]]
                )
        # If still at a customer with freight needs for new tour, reload via depot.
        if anchor.node != instance.depot_id and customers:
            for base in list(skeletons):
                skeletons.append([Visit(instance.depot_id, "reload"), *base])
        for visits in skeletons:
            res = evaluate_route(instance, anchor, visits, energy)
            best = max(best, _route_value(res))
    if not must_serve:
        res = evaluate_route(instance, anchor, [], energy)
        best = max(best, _route_value(res))
    return best


def _apply_first_action(
    spec: ForkSpec,
    action: str,
    energy: NominalLinearEnergy,
) -> tuple[PrefixResult, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    anchor = spec.observation.vehicles[0].anchor
    accepted = list(spec.observation.accepted)
    rejected: list[str] = []
    notes: list[str] = []

    if action == "serve_near":
        pref = simulate_prefix(spec.instance, anchor, [Visit("Near", "service")], energy)
        if pref.feasible and "Near" not in accepted:
            accepted.append("Near")
        notes.append("serve_near_prefix")
        return pref, tuple(accepted), tuple(rejected), tuple(notes)

    if action == "charge_first":
        pref = simulate_prefix(spec.instance, anchor, [Visit("S", "charge")], energy)
        notes.append("charge_first_prefix")
        return pref, tuple(accepted), tuple(rejected), tuple(notes)

    if action == "accept_now":
        pref = simulate_prefix(spec.instance, anchor, [Visit("Now", "service")], energy)
        if pref.feasible and "Now" not in accepted:
            accepted.append("Now")
        notes.append("accept_now_prefix")
        return pref, tuple(accepted), tuple(rejected), tuple(notes)

    if action == "reject_now":
        rejected.append("Now")
        pref = PrefixResult(True, "reject_noop", anchor, (), 0.0, 0.0)
        notes.append("reject_now")
        return pref, tuple(accepted), tuple(rejected), tuple(notes)

    raise ValueError(f"unknown action {action}")


def _scenario_value(
    spec: ForkSpec,
    action: str,
    scenario: tuple[tuple[str, float], ...],
    *,
    energy: NominalLinearEnergy,
) -> float:
    pref, accepted, rejected, _notes = _apply_first_action(spec, action, energy)
    if not pref.feasible:
        return -1e9

    realized = SERVICE_REWARD * len(pref.served) - DISTANCE_PENALTY * pref.distance - CHARGE_PENALTY * pref.charge_time
    done = set(pref.served)

    must = [c for c in accepted if c not in done]
    optional: list[str] = []
    for cid in spec.observation.released_open:
        if cid in done or cid in rejected or cid in must:
            continue
        optional.append(cid)
    for cid, _release_t in scenario:
        if cid in done or cid in rejected or cid in must or cid in optional:
            continue
        # Causal: scenario customer may be planned only as an optional opportunity;
        # evaluate_route enforces ready/due — release before ready is modeled by window.ready.
        optional.append(cid)

    suffix = _best_suffix_value(
        spec.instance,
        pref.anchor,
        must_serve=tuple(must),
        optional=tuple(optional),
        energy=energy,
    )
    return realized + suffix


def score_action(spec: ForkSpec, action: str, *, energy: NominalLinearEnergy | None = None) -> ActionScore:
    model = energy or NominalLinearEnergy()
    pref, _acc, _rej, notes = _apply_first_action(spec, action, model)
    per = tuple(_scenario_value(spec, action, sc, energy=model) for sc in spec.scenarios)
    return ActionScore(
        action=action,
        reactive_value=per[0],
        stochastic_value=sum(p * v for p, v in zip(spec.scenario_probs, per, strict=True)),
        safe=pref.feasible,
        per_scenario=per,
        notes=notes,
    )


def choose_policies(spec: ForkSpec) -> PolicyChoice:
    scores = tuple(score_action(spec, a) for a in spec.candidate_actions)
    safe_scores = [s for s in scores if s.safe]
    if not safe_scores:
        raise RuntimeError(f"no safe actions for {spec.case_id}")
    reactive = max(safe_scores, key=lambda s: (s.reactive_value, s.action)).action
    stochastic = max(safe_scores, key=lambda s: (s.stochastic_value, s.action)).action
    mpc = max(safe_scores, key=lambda s: (s.stochastic_value, s.action)).action
    return PolicyChoice(
        reactive=reactive,
        stochastic_rollout=stochastic,
        commitment_safe_mpc=mpc,
        reactive_equals_stochastic=(reactive == stochastic),
        mpc_equals_stochastic=(mpc == stochastic),
        scores=scores,
    )


def gate_report(specs: list[ForkSpec] | None = None) -> dict:
    from safe_time_evrp.mpc_central.forks import all_forks

    forks = specs or all_forks()
    rows = []
    for spec in forks:
        choice = choose_policies(spec)
        rows.append(
            {
                "case_id": spec.case_id,
                "reactive": choice.reactive,
                "stochastic_rollout": choice.stochastic_rollout,
                "commitment_safe_mpc": choice.commitment_safe_mpc,
                "prediction_changes_action": not choice.reactive_equals_stochastic,
                "mpc_differs_from_rollout": not choice.mpc_equals_stochastic,
                "scores": [
                    {
                        "action": s.action,
                        "reactive_value": s.reactive_value,
                        "stochastic_value": s.stochastic_value,
                        "safe": s.safe,
                        "per_scenario": list(s.per_scenario),
                    }
                    for s in choice.scores
                ],
            }
        )
    n_div = sum(1 for r in rows if r["prediction_changes_action"])
    n_mpc_diff = sum(1 for r in rows if r["mpc_differs_from_rollout"])
    if n_div == 0:
        verdict = "NO-GO"
        reason = "Prediction does not change executable first actions vs reactive on the forks."
    elif n_mpc_diff == 0:
        verdict = "REVISE"
        reason = (
            "Prediction changes first actions vs reactive, but commitment-safe MPC "
            "coincides with standard stochastic rollout — no Phase-3 novelty vs rollout."
        )
    else:
        verdict = "GO"
        reason = "MPC rule differs from both reactive and standard rollout on at least one fork."
    return {
        "verdict": verdict,
        "reason": reason,
        "n_forks": len(rows),
        "n_prediction_diverges_from_reactive": n_div,
        "n_mpc_differs_from_rollout": n_mpc_diff,
        "rows": rows,
    }
