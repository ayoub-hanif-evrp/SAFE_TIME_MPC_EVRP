"""Candidate structural mechanism and novelty confrontation.

Candidate: Certified information-aware route selection with commitment-preserving
continuation under a shared energy-parameter uncertainty set.

Claim under investigation: an informative first action is admissible only if a
continuation covering accepted deliveries remains feasible for every theta in
the current uncertainty set; among admissible actions, maximize expected
operational value including the value of the posterior update.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dual_mpc.exact_oracle import DualToyParams, FirstAction, run_exact_dual_example


@dataclass(frozen=True)
class MechanismAssessment:
    name: str
    reduces_to_known_safe_dual_control: bool
    reduces_to_akerblom_navigation_learning: bool
    new_theorem_proved: bool
    phenomenon_demonstrated: bool
    distinctive_evrp_coupling: bool
    verdict: str
    notes: tuple[str, ...]


def assess_mechanism() -> MechanismAssessment:
    report = run_exact_dual_example(DualToyParams())
    phenomenon = bool(report.information_changes_first_action and report.dual_differs_from_passive)
    # Honest assessment: the computational rule is Bayes-adaptive maximization over
    # actions that preserve a robust continuation for accepted customers under Θ.
    # That is constrained dual control / safe learning-MPC applied to EVRP toys.
    # Åkerblom et al. already cover Bayesian EV energy learning + multi-agent sharing
    # for navigation (not TW/commitments/charging admission). Our coupling is a
    # problem-setting contribution; it is not yet a new dominance theorem or
    # complexity-reducing certificate beyond standard set-membership safety filters.
    return MechanismAssessment(
        name="certified_info_aware_route_with_commitment_continuation",
        reduces_to_known_safe_dual_control=True,
        reduces_to_akerblom_navigation_learning=False,  # problem class differs (TW/commitments)
        new_theorem_proved=False,
        phenomenon_demonstrated=phenomenon,
        distinctive_evrp_coupling=phenomenon,  # SOC+charge time+due+commitment on the toy
        verdict=("STOP_HUMAN_DECISION" if phenomenon else "STOP_NO_PHENOMENON"),
        notes=(
            "Exact toy: safe dual selects INFORM; safe passive selects EXPLOIT.",
            "Rule = max E[V|posterior] over actions with commitment backup under Θ.",
            "No new label-dominance or complexity theorem proved.",
            "Differentiation from Åkerblom: irrevocable TW commitments + charging time tradeoff.",
            "Differentiation is not yet sufficient for autonomous GO to large evaluation.",
            f"dual_first={None if report.safe_dual_first is None else report.safe_dual_first.value}",
            f"passive_first={None if report.safe_passive_first is None else report.safe_passive_first.value}",
        ),
    )


def counterexamples_catalog() -> list[dict]:
    """Documented qualitative counterexamples (not all encoded as separate oracles)."""
    return [
        {
            "name": "info_large_but_useless",
            "description": (
                "Informative arc reveals theta but no future decision depends on theta "
                "(no optional C, no charge fork) → dual equals passive."
            ),
        },
        {
            "name": "info_worth_paying",
            "description": (
                "Canonical DualToyParams: paying +2 time / possible +3 energy reveals theta "
                "and enables optional C when theta=0."
            ),
            "encoded_in": "exact_oracle.DualToyParams",
        },
        {
            "name": "exploration_unsafe",
            "description": (
                "If INFORM energy under theta=1 exceeded battery, INFORM excluded by "
                "commitment filter; dual cannot explore."
            ),
        },
        {
            "name": "exploration_safe_not_worthwhile",
            "description": ("If reward_c is tiny, dual value of INFORM can fall below EXPLOIT even if safe."),
        },
        {
            "name": "cross_vehicle_information",
            "description": (
                "Not exact-solved here: EV1 INFORM observation updates shared belief used by EV2. "
                "Åkerblom already studies multi-agent energy learning for navigation."
            ),
        },
    ]


def first_action_name(action: FirstAction | None) -> str | None:
    return None if action is None else action.value
