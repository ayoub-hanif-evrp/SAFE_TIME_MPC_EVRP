"""Witness-based commitment viability / recoverable flexibility probes.

Resources measured from a validated nominal continuation witness:

* **time slack** — min (window.due - projected service completion) over planned services
* **SOC residual** — min end-of-route SOC across vehicles
* **charge time** — total planned charge duration in the witness
* **load residual** — capacity minus peak onboard demand in planned services

These are exact under the simulator's nominal linear energy and Euclidean physics
assumptions for the *witness plan*, not disturbance-robust certificates.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation


@dataclass(frozen=True)
class ViabilityProfile:
    commitment_ok: bool
    min_window_slack: float | None
    min_end_soc: float | None
    total_charge_time: float
    min_load_residual: float | None
    n_planned_services: int
    reasons: tuple[str, ...]


def profile_decision_viability(
    instance: Instance,
    observation: Observation,
    decision: Decision,
    *,
    horizon: float,
    energy: NominalLinearEnergy | None = None,
) -> ViabilityProfile:
    model = energy or NominalLinearEnergy()
    public = make_public_snapshot(instance, observation, horizon).instance
    report = validate_continuation(
        public,
        observation,
        decision.routes,
        energy=model,
        require_new=frozenset(decision.newly_accepted),
    )
    if not report.ok:
        return ViabilityProfile(
            commitment_ok=False,
            min_window_slack=None,
            min_end_soc=None,
            total_charge_time=0.0,
            min_load_residual=None,
            n_planned_services=0,
            reasons=tuple(report.reasons),
        )

    slacks: list[float] = []
    end_socs: list[float] = []
    load_res: list[float] = []
    charge = 0.0
    n_svc = 0
    cap = public.vehicle_type.load_capacity
    for vehicle in observation.vehicles:
        visits = list(decision.routes.get(vehicle.id, []))
        n_svc += sum(1 for v in visits if v.purpose == "service")
        result = evaluate_route(public, vehicle.anchor, visits, model)
        if not result.feasible:
            return ViabilityProfile(
                False,
                None,
                None,
                0.0,
                None,
                n_svc,
                (f"route_infeasible:{vehicle.id}:{result.reason}",),
            )
        end_socs.append(result.end_soc)
        charge += result.charge_time
        # Conservative slack proxy: route end time versus each planned customer's due date.
        for vis in visits:
            if vis.purpose != "service":
                continue
            node = public.node(vis.node_id)
            slacks.append(node.window.due - result.end_time)
        demand = sum(public.node(v.node_id).demand for v in visits if v.purpose == "service")
        load_res.append(cap - (vehicle.load + demand))

    return ViabilityProfile(
        commitment_ok=True,
        min_window_slack=min(slacks) if slacks else None,
        min_end_soc=min(end_socs) if end_socs else None,
        total_charge_time=charge,
        min_load_residual=min(load_res) if load_res else None,
        n_planned_services=n_svc,
        reasons=(),
    )


def viability_dominates(a: ViabilityProfile, b: ViabilityProfile) -> bool:
    """Strict multi-resource dominance (all measured resources weakly better, one strict)."""
    if not a.commitment_ok or not b.commitment_ok:
        return False
    comps: list[tuple[float | None, float | None]] = [
        (a.min_window_slack, b.min_window_slack),
        (a.min_end_soc, b.min_end_soc),
        (a.min_load_residual, b.min_load_residual),
        # Less charge time is more flexible residual charger budget.
        (-a.total_charge_time, -b.total_charge_time),
    ]
    weakly = True
    strict = False
    for xa, xb in comps:
        if xa is None or xb is None:
            continue
        if xa < xb - 1e-9:
            weakly = False
            break
        if xa > xb + 1e-9:
            strict = True
    return weakly and strict


def analyze_viability_vs_rollout_ranking(
    instance: Instance,
    observation: Observation,
    ranked: list[tuple[str, Decision, float]],
    *,
    horizon: float,
    energy: NominalLinearEnergy | None = None,
) -> dict:
    """Check whether witness viability distinguishes actions beyond rollout value order.

    Proposition tested (informal): under nominal physics, a validated continuation
    witness certifies immediate commitment coverage and residual resources *of that
    plan*, but does not by itself reorder actions relative to causal rollout value
    unless those residual metrics differ while rollout values tie or disagree.
    """
    profiles = []
    for name, dec, value in ranked:
        prof = profile_decision_viability(instance, observation, dec, horizon=horizon, energy=energy)
        profiles.append(
            {
                "name": name,
                "rollout_value": value,
                "commitment_ok": prof.commitment_ok,
                "min_window_slack": prof.min_window_slack,
                "min_end_soc": prof.min_end_soc,
                "total_charge_time": prof.total_charge_time,
                "min_load_residual": prof.min_load_residual,
                "n_planned_services": prof.n_planned_services,
            }
        )
    # Compare adjacent rollout ranks for viability disagreement.
    disagreements = 0
    dominance_flips = 0
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            ni, di, vi = ranked[i]
            nj, dj, vj = ranked[j]
            pi = profile_decision_viability(instance, observation, di, horizon=horizon, energy=energy)
            pj = profile_decision_viability(instance, observation, dj, horizon=horizon, energy=energy)
            if abs(vi - vj) <= 1e-9 and viability_dominates(pi, pj):
                disagreements += 1
            if vi > vj + 1e-9 and viability_dominates(pj, pi):
                dominance_flips += 1

    if dominance_flips == 0 and disagreements == 0:
        contribution = "NO_ADDITIONAL_SIGNAL"
        proposition = (
            "Under the FleetSimulator nominal linear energy model, witness residual "
            "resources (window slack, end SOC, charge time, load residual) did not "
            "distinguish or reorder actions beyond ordinary commitment feasibility plus "
            "causal rollout value on the probed epoch."
        )
    elif dominance_flips > 0:
        contribution = "DISAGREES_WITH_ROLLOUT"
        proposition = (
            "Witness residual-resource dominance disagreed with causal rollout ranking "
            "on at least one action pair — viability metrics can flag scarce flexibility "
            "not captured by expected rollout value alone on this epoch."
        )
    else:
        contribution = "BREAKS_VALUE_TIES"
        proposition = (
            "Witness residual resources break rollout-value ties but do not reverse "
            "strict rollout rankings on the probed epoch."
        )
    return {
        "profiles": profiles,
        "tie_breaks": disagreements,
        "dominance_flips": dominance_flips,
        "contribution": contribution,
        "proposition": proposition,
    }
