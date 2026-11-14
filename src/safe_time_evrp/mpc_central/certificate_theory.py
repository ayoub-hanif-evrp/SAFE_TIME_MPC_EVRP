"""Formal commitment-certificate definitions — corrected closeout statement.

The original ``NominalCommitmentInvariance`` claim was stronger than the
implemented controller supports: certificates can invalidate, decide() can emit
``UNKNOWN`` while accepted customers remain pending, and horizon residuals may
fail. This module states what *is* proved for the actual code path.
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
    "public_information_only_at_decision_epochs",
    "validate_continuation_is_sound_for_nominal_suffix_feasibility",
)


@dataclass(frozen=True)
class TheoremStatement:
    name: str
    claim: str
    assumptions: tuple[str, ...]
    proof: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    what_is_not_claimed: tuple[str, ...]
    supported_by_plant: bool
    counterexample: str | None = None


# Corrected proposition (replaces overstated NominalCommitmentInvariance).
CONDITIONAL_CERTIFICATE_VALIDITY = TheoremStatement(
    name="ConditionalCertificateValidity",
    claim=(
        "At any decision epoch where the controller emits status CERTIFIED_FEASIBLE for "
        "observation o and decision d, and an independent call to validate_continuation(o, d.routes, "
        "require_new=d.newly_accepted) returns ok under nominal physics, the published "
        "ContinuationCertificate's routes cover every customer in "
        "pending(o) ∪ d.newly_accepted, where pending(o) = accepted(o) \\ (completed(o) ∪ in_service(o)). "
        "Coverage means each such customer is either already IN_SERVICE or appears as a future "
        "service visit in the certified suffixes. This is a per-epoch conditional validity "
        "proposition for certified claims — not an unconditional invariant across all epochs."
    ),
    assumptions=ASSUMPTIONS,
    proof=(
        "Definition. Let pending(o) and newly = d.newly_accepted. The controller's emit path "
        "sets status=CERTIFIED_FEASIBLE only after validate_continuation(..., require_new=newly) "
        "returns ok (independent verify before publish).",
        "By the semantics of validate_continuation (continuation_validate.py): pending obligations "
        "are pending(o); require_new adds newly; coverage is served_all ∪ in_service(o); "
        "missing = (pending(o) ∪ newly) \\ covered must be empty for ok=True; duplicate service "
        "and illegal new accepts are rejected.",
        "Therefore, whenever the controller publishes a certificate under CERTIFIED_FEASIBLE, "
        "the independently verified routes cover pending(o) ∪ newly at that epoch.",
        "Publish records accepted := accepted(o) ∪ newly (post-decision set), so the certificate "
        "object's accepted field matches the obligations that were certified.",
        "QED (conditional on the certified-claim gate firing). This proof does not extend to "
        "epochs where status=UNKNOWN or the store is empty.",
    ),
    failure_conditions=(
        "CertificateStore.advance_or_invalidate may clear the certificate when accepted "
        "obligations appear dropped without completion/rejection, or when revalidation fails.",
        "decide() may return UNKNOWN with pending accepted customers when no scored feasible "
        "candidate exists and fallback revalidation fails — obligations may remain uncovered "
        "until a later epoch recovers or the episode records accepted-unfulfilled.",
        "Horizon-end residual probes may fail; accepted-unfulfilled is then honest plant state, "
        "not a certified continuation.",
        "Busy-vehicle / mid-action epochs can invalidate advanced suffixes relative to new anchors.",
    ),
    what_is_not_claimed=(
        "Unconditional preservation of a feasible plan at every decision epoch.",
        "Robustness to energy/travel disturbances or forecast misspecification.",
        "That UNKNOWN epochs cannot occur while accepted customers remain pending.",
        "Global multistage optimality of economic selection.",
        "Novelty of CertificateStore relative to M1 (same store object).",
    ),
    supported_by_plant=True,
    counterexample=(
        "Concrete failure of the stronger (withdrawn) unconditional claim: on A_low_soc_charge "
        "seed 7 around t≈73.03 (arrive), CC-E-MPC emitted UNKNOWN while C4 and C5 remained "
        "accepted and store.current was absent — so preservation-at-every-epoch is false for "
        "the implemented controller. After accounting fixes, such epochs must be labeled "
        "obligation gaps, not CERTIFIED_FEASIBLE."
    ),
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
    pending = set(observation.accepted) - set(observation.completed) - set(observation.in_service)
    cert_pending = set(certificate.accepted) - set(observation.completed) - set(observation.in_service)
    return {
        "ok": report.ok,
        "status": report.status,
        "reasons": list(report.reasons),
        "version": certificate.version,
        "n_pending_accepted": len(pending),
        "certificate_accepted_includes_pending": pending <= cert_pending | set(observation.in_service),
    }


def theorem_document() -> dict:
    t = CONDITIONAL_CERTIFICATE_VALIDITY
    return {
        "name": t.name,
        "claim": t.claim,
        "assumptions": list(t.assumptions),
        "proof": list(t.proof),
        "failure_conditions": list(t.failure_conditions),
        "what_is_not_claimed": list(t.what_is_not_claimed),
        "supported_by_plant": t.supported_by_plant,
        "counterexample": t.counterexample,
        "withdrawn_claim": (
            "NominalCommitmentInvariance (unconditional preservation at every epoch) — "
            "withdrawn; contradicted by UNKNOWN-with-accepted epochs."
        ),
        "certificate_object": (
            "ContinuationCertificate: versioned routes, served set, per-vehicle anchors, "
            "post-decision accepted set, assumptions — a persisted executable continuation."
        ),
    }
