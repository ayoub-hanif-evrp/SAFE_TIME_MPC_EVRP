"""Formal commitment-certificate definitions and nominal feasibility claim.

This module states the theorem that the simulator and controller actually support.
It does **not** claim uncertainty-robust recursive feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.certificate_store import ContinuationCertificate
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation

ASSUMPTIONS = (
    "nominal_linear_energy",
    "deterministic_euclidean_travel_and_energy",
    "independent_chargers_no_station_capacity",
    "noninterruptible_locked_travel_service_charge",
    "deadlines_are_customer_window_due_dates",
    "episode_ends_at_finite_horizon_or_idle_completion",
    "accept_only_with_complete_feasible_updated_certificate",
    "public_information_only_at_decision_epochs",
)


@dataclass(frozen=True)
class TheoremStatement:
    name: str
    claim: str
    assumptions: tuple[str, ...]
    induction_sketch: tuple[str, ...]
    what_is_not_claimed: tuple[str, ...]
    supported_by_plant: bool
    counterexample: str | None = None


NOMINAL_COMMITMENT_INVARIANCE = TheoremStatement(
    name="NominalCommitmentInvariance",
    claim=(
        "Let C_k be a ContinuationCertificate that validate_continuation accepts at "
        "decision epoch k for observation o_k under nominal physics. Suppose the "
        "controller (i) advances C_k through realized noninterruptible events via "
        "CertificateStore.advance_or_invalidate, (ii) accepts a customer only when a "
        "complete updated certificate C_{k+1} validates coverage of all pending "
        "accepted and newly accepted obligations, and (iii) otherwise executes a "
        "validated fallback certificate. Then, under exact nominal transition dynamics "
        "matching FleetSimulator, every accepted obligation retains a feasible "
        "completion plan at every subsequent decision epoch until it is completed, "
        "rejected under the plant reject rules, or the episode terminates with a "
        "validated residual continuation (or is recorded accepted-unfulfilled when "
        "residual validation fails at horizon end)."
    ),
    assumptions=ASSUMPTIONS,
    induction_sketch=(
        "Base: at the first accept, validate_continuation certifies a full fleet suffix "
        "covering pending ∪ newly accepted customers from current/post-action anchors.",
        "Inductive step (physical event): locked travel/service/charge completes exactly "
        "as recorded; advance_or_invalidate strips realized visits; revalidation from "
        "the new anchors succeeds or the certificate is invalidated and the controller "
        "must not claim coverage without a new validated plan.",
        "Inductive step (decision): a candidate is executed only if validate_continuation "
        "succeeds with require_new; otherwise the previously validated advanced certificate "
        "is executed (fallback), preserving coverage of already accepted obligations.",
        "Accepts never resurrect rejected customers; in-service customers are covered by "
        "the ongoing noninterruptible service and are not re-admitted.",
    ),
    what_is_not_claimed=(
        "Robustness to energy/travel disturbances or forecast misspecification.",
        "Global multistage optimality of the economic selection rule.",
        "That residual horizon-end probes cannot fail (accepted-unfulfilled may occur).",
        "Novelty of expected-value stochastic rollout by itself.",
    ),
    supported_by_plant=True,
    counterexample=None,
)


def check_certificate_feasible(
    instance: Instance,
    observation: Observation,
    certificate: ContinuationCertificate | None,
    *,
    horizon: float,
    energy: NominalLinearEnergy | None = None,
) -> dict:
    if certificate is None:
        return {"ok": False, "reason": "no_certificate"}
    public = make_public_snapshot(instance, observation, horizon).instance
    report = validate_continuation(public, observation, certificate.routes, energy=energy)
    return {
        "ok": report.ok,
        "status": report.status,
        "reasons": list(report.reasons),
        "version": certificate.version,
        "n_pending_accepted": len(set(observation.accepted) - set(observation.completed) - set(observation.in_service)),
    }


def theorem_document() -> dict:
    t = NOMINAL_COMMITMENT_INVARIANCE
    return {
        "name": t.name,
        "claim": t.claim,
        "assumptions": list(t.assumptions),
        "induction_sketch": list(t.induction_sketch),
        "what_is_not_claimed": list(t.what_is_not_claimed),
        "supported_by_plant": t.supported_by_plant,
        "counterexample": t.counterexample,
        "certificate_object": (
            "ContinuationCertificate: versioned routes, served set, per-vehicle anchors, "
            "accepted set, assumptions — a persisted executable continuation, not a metric."
        ),
    }
