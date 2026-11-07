"""Decision-relevant information-value upper bounds (EVRP resource structure).

Generic pruning fact (NOT claimed as novel)
-------------------------------------------
If L is a verified lower bound on the optimal value and Q_bar(a) >= Q*(a) with
Q_bar(a) <= L, then a cannot strictly improve the incumbent.

Proposed EVRP-specific construction (research object)
-----------------------------------------------------
DRUB — Decision-Relevant Upper Bound after first travel action a:

  Q_bar(a) = E_theta[ travel_reward(a,theta) + V_OL(x_a(theta), theta) ]

where V_OL is the best open-loop continuation in the declared plan family
under known theta from the post-travel state. Under zero noise and
deterministic latent regimes, after an informative segment the posterior is
Dirac and this equals the exact Bayes continuation; after an uninformative
segment it is optimistic relative to a nonanticipative robust continuation
(because it allows theta-contingent plans without further observations).

Zero decision-relevance certificate (sound, cheap)
--------------------------------------------------
If for every theta in prior support,
  V_OL(x_a(theta), theta) == V_robust(x_a_phys, Theta)
when evaluated at the same physical post-travel state (SOC/time/node), then
learning cannot improve the continuation family after a. Combined with travel
cost comparisons this can prune purely informative detours.

Essential assumptions: finite theta support; listed continuation family;
observations only after completed travel; no retroactive corridor change.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.exact_oracle import _continuation_value_known_theta, _robust_continuation_ok
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


@dataclass(frozen=True)
class DecisionRelevantBound:
    action_key: str
    q_bar: float
    zero_voi_certificate: bool
    robust_continuation_value: float
    clairvoyant_continuation_mean: float
    sound_under_assumptions: bool
    notes: tuple[str, ...]


def _physical_state_with_prior_belief(state: WorldState, prior: DiscreteBelief) -> WorldState:
    return WorldState(
        vehicles=state.vehicles,
        accepted=state.accepted,
        completed=state.completed,
        rejected=state.rejected,
        announced=state.announced,
        belief=prior,
        stage=state.stage,
    )


def evaluate_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> DecisionRelevantBound | None:
    """Compute DRUB for a candidate first travel action."""
    prior = state.belief
    travel_rewards = []
    clair_conts = []
    robust_conts = []
    for theta, p in zip(prior.support, prior.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        if not tr.ok or tr.state is None:
            return None
        if not _robust_continuation_ok(net, tr.state):
            # Unsafe first action — no finite bound used for pruning optimum among safe set
            return None
        v_ol = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
        if v_ol < -1e8:
            return None
        # Robust value from same physical state denying information
        forced = _physical_state_with_prior_belief(tr.state, prior)
        rob_vals = [_continuation_value_known_theta(net, forced, th, noise=noise) for th in prior.support_set()]
        v_rob = min(rob_vals) if rob_vals else float("-inf")
        travel_rewards.append((p, tr.reward_delta))
        clair_conts.append((p, v_ol))
        robust_conts.append((p, v_rob))

    q_bar = sum(p * (tr + vc) for (p, tr), (_, vc) in zip(travel_rewards, clair_conts, strict=True))
    # Expected robust continuation + travel (passive-style score components)
    q_rob = sum(p * (tr + vr) for (p, tr), (_, vr) in zip(travel_rewards, robust_conts, strict=True))
    # Zero VoI: for every theta, OL value equals robust value at that physical state
    zero_voi = True
    for theta, p in zip(prior.support, prior.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        assert tr.ok and tr.state is not None
        v_ol = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
        forced = _physical_state_with_prior_belief(tr.state, prior)
        v_rob = min(_continuation_value_known_theta(net, forced, th, noise=noise) for th in prior.support_set())
        if abs(v_ol - v_rob) > 1e-9:
            zero_voi = False
            break

    return DecisionRelevantBound(
        action_key=action.key(),
        q_bar=q_bar,
        zero_voi_certificate=zero_voi,
        robust_continuation_value=q_rob,
        clairvoyant_continuation_mean=sum(p * vc for p, vc in clair_conts),
        sound_under_assumptions=True,
        notes=(
            "DRUB=E[travel+V_OL|theta]",
            "sound_vs_exact_when_continuation_family_matches_oracle",
            "optimistic_if_uninformative_and_causal_must_be_robust",
            f"zero_voi={zero_voi}",
        ),
    )


def bound_dominates_true_q(q_bar: float, true_q: float, *, tol: float = 1e-9) -> bool:
    """Validity test: claimed upper bound must be >= true Q."""
    return q_bar + tol >= true_q
