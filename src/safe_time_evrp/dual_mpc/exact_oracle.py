"""Exact tiny dual-control oracle for EVRP with shared energy parameter.

Instance family (documented restriction)
---------------------------------------
1 EV, customers A (accepted commitment) and C (optional), 1 charger S,
two D→A corridors (exploit vs inform), discrete theta in {0,1}, zero noise,
deterministic time. Exactness is **global within this finite decision tree**,
not a general continuous EVRP optimum.

Scientific question
-------------------
Does a safe dual policy select the informative corridor because of future
charging / optional-delivery value, while a safe passive learner that only
exploits does not — under the same commitment safety contract?
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.dual_mpc.belief import DiscreteBelief
from safe_time_evrp.dual_mpc.energy_param import ArcFeature, SharedThetaWorld


class OracleStatus(str, Enum):
    EXACT = "EXACT"
    UNKNOWN = "UNKNOWN"


class FirstAction(str, Enum):
    EXPLOIT = "exploit_D_A"
    INFORM = "inform_D_A"


@dataclass(frozen=True)
class DualToyParams:
    battery: float = 12.0
    start_soc: float = 12.0
    # Path energies: e = base + informative * theta
    exploit: ArcFeature = ArcFeature("DA_exploit", base=4.0, informative=0.0)
    inform: ArcFeature = ArcFeature("DA_inform", base=3.0, informative=3.0)
    ac: ArcFeature = ArcFeature("AC", base=6.0, informative=3.0)
    # Times
    time_exploit: float = 10.0
    time_inform: float = 12.0  # slightly slower
    time_ac: float = 8.0
    time_charge: float = 15.0  # full top-up duration proxy
    service_a: float = 1.0
    service_c: float = 1.0
    due_a: float = 100.0
    due_c: float = 28.0  # tight: charging after A misses C
    charge_target: float = 12.0
    theta_support: tuple[float, ...] = (0.0, 1.0)
    reward_a: float = 10.0
    reward_c: float = 5.0
    energy_cost: float = 0.1  # mild preference for less energy


@dataclass(frozen=True)
class DualControlExactReport:
    status: OracleStatus
    clairvoyant_value: float | None
    certainty_equivalent_first: FirstAction | None
    safe_passive_first: FirstAction | None
    safe_dual_first: FirstAction | None
    exact_optimum_first: FirstAction | None
    safe_passive_value: float | None
    safe_dual_value: float | None
    exact_value: float | None
    dual_differs_from_passive: bool
    information_changes_first_action: bool
    commitment_safe: bool
    phenomenon_ev_specific: bool
    notes: tuple[str, ...]


def _energy(feature: ArcFeature, theta: float) -> float:
    return feature.base + feature.informative * theta


def _path_feasible_for_all(feature: ArcFeature, thetas: frozenset[float], soc: float) -> bool:
    return all(_energy(feature, th) <= soc + 1e-12 for th in thetas)


def _arrive_serve_a(params: DualToyParams, path: FirstAction, theta: float) -> tuple[float, float, float]:
    """Return (soc_after_A, time_after_A, energy_used) if A served, else raise."""
    feat = params.exploit if path is FirstAction.EXPLOIT else params.inform
    travel_t = params.time_exploit if path is FirstAction.EXPLOIT else params.time_inform
    e = _energy(feat, theta)
    if e > params.start_soc + 1e-12:
        raise RuntimeError("A unreachable")
    soc = params.start_soc - e
    t = travel_t + params.service_a
    if t > params.due_a + 1e-12:
        raise RuntimeError("A late")
    return soc, t, e


def _can_serve_c_without_charge(params: DualToyParams, soc: float, t: float, theta: float) -> bool:
    e = _energy(params.ac, theta)
    if e > soc + 1e-12:
        return False
    t2 = t + params.time_ac + params.service_c
    return t2 <= params.due_c + 1e-12


def _can_serve_c_with_charge(params: DualToyParams, soc: float, t: float, theta: float) -> bool:
    # Charge to target then A→C; charging makes C late by design when due_c is tight.
    if params.charge_target < soc - 1e-12:
        return False
    t_after_charge = t + params.time_charge
    e = _energy(params.ac, theta)
    soc2 = params.charge_target - e
    if soc2 < -1e-12:
        return False
    t2 = t_after_charge + params.time_ac + params.service_c
    return t2 <= params.due_c + 1e-12


def _posterior_value_after_path(
    params: DualToyParams,
    path: FirstAction,
    belief: DiscreteBelief,
    *,
    safe: bool,
) -> float:
    """Expected reward of optimal continuation after taking ``path`` and updating belief.

    Safe continuation: may serve C only if feasible for **all** remaining support thetas
    without violating commitment (A already served). Otherwise skip C or charge if that
    preserves safety (here charge misses C → skip).
    """
    feat = params.exploit if path is FirstAction.EXPLOIT else params.inform
    total = 0.0
    for theta, p in zip(belief.support, belief.probs, strict=True):
        if p <= 0:
            continue
        world = SharedThetaWorld(theta_star=theta)
        e_obs = world.realize(feat)
        soc, t, _ = _arrive_serve_a(params, path, theta)
        post = belief.update_from_observation(feat, e_obs, noise_tol=1e-9)
        rem = post.support_set()
        reward = params.reward_a - params.energy_cost * e_obs
        # Decide whether to attempt C
        if safe:
            # Serve C without charge only if feasible under every remaining theta.
            ok_all = all(_can_serve_c_without_charge(params, soc, t, th) for th in rem)
            if ok_all and rem:
                # True theta also feasible (rem contains truth after perfect obs on inform)
                if _can_serve_c_without_charge(params, soc, t, theta):
                    reward += params.reward_c
            # else skip C (charging cannot recover due window)
        else:
            # Certainty-equivalent / risk-taking: use posterior mean theta for C decision
            th_hat = post.mean()
            if _can_serve_c_without_charge(params, soc, t, th_hat) and _can_serve_c_without_charge(
                params, soc, t, theta
            ):
                reward += params.reward_c
            elif _can_serve_c_without_charge(params, soc, t, th_hat) and not _can_serve_c_without_charge(
                params, soc, t, theta
            ):
                # CE wrongly attempts C → energy infeasible → fail C, keep A only
                pass
        total += p * reward
    return total


def _clairvoyant_value(params: DualToyParams, prior: DiscreteBelief) -> float:
    total = 0.0
    for theta, p in zip(prior.support, prior.probs, strict=True):
        best = float("-inf")
        for path in (FirstAction.EXPLOIT, FirstAction.INFORM):
            soc, t, e = _arrive_serve_a(params, path, theta)
            reward = params.reward_a - params.energy_cost * e
            if _can_serve_c_without_charge(params, soc, t, theta):
                reward += params.reward_c
            best = max(best, reward)
        total += p * best
    return total


def _safe_first_actions(params: DualToyParams, prior: DiscreteBelief) -> list[FirstAction]:
    thetas = prior.support_set()
    out: list[FirstAction] = []
    if _path_feasible_for_all(params.exploit, thetas, params.start_soc):
        out.append(FirstAction.EXPLOIT)
    if _path_feasible_for_all(params.inform, thetas, params.start_soc):
        out.append(FirstAction.INFORM)
    return out


def run_exact_dual_example(params: DualToyParams | None = None) -> DualControlExactReport:
    """Compute exact values for clairvoyant / CE / safe-passive / safe-dual on the toy."""
    params = params or DualToyParams()
    prior = DiscreteBelief.uniform(params.theta_support)
    safe_actions = _safe_first_actions(params, prior)
    if not safe_actions:
        return DualControlExactReport(
            status=OracleStatus.EXACT,
            clairvoyant_value=None,
            certainty_equivalent_first=None,
            safe_passive_first=None,
            safe_dual_first=None,
            exact_optimum_first=None,
            safe_passive_value=None,
            safe_dual_value=None,
            exact_value=None,
            dual_differs_from_passive=False,
            information_changes_first_action=False,
            commitment_safe=False,
            phenomenon_ev_specific=False,
            notes=("no_safe_path_to_A_under_prior_support",),
        )

    clair = _clairvoyant_value(params, prior)

    # Certainty-equivalent first action: evaluate each path under mean theta only (unsafe potential)
    th_mean = prior.mean()
    ce_scores: dict[FirstAction, float] = {}
    for path in (FirstAction.EXPLOIT, FirstAction.INFORM):
        # One-shot CE: pretend theta = mean, then score; not a safe policy
        try:
            soc, t, e = _arrive_serve_a(params, path, th_mean)
        except RuntimeError:
            ce_scores[path] = float("-inf")
            continue
        r = params.reward_a - params.energy_cost * e
        if _can_serve_c_without_charge(params, soc, t, th_mean):
            r += params.reward_c
        ce_scores[path] = r
    ce_first = max(ce_scores, key=lambda a: ce_scores[a])

    # Safe passive: among safe first actions, prefer exploit (no intentional information)
    # Value = Bayesian expected reward with safe continuations.
    passive_candidates = [a for a in safe_actions if a is FirstAction.EXPLOIT] or list(safe_actions)
    passive_first = passive_candidates[0]
    passive_value = _posterior_value_after_path(params, passive_first, prior, safe=True)

    # Safe dual / exact Bayes-adaptive: maximize expected value over safe first actions,
    # accounting for belief updates (information value).
    dual_scores = {a: _posterior_value_after_path(params, a, prior, safe=True) for a in safe_actions}
    dual_first = max(dual_scores, key=lambda a: dual_scores[a])
    dual_value = dual_scores[dual_first]
    exact_first = dual_first
    exact_value = dual_value

    differs = dual_first is not passive_first
    info_matters = differs and dual_value > passive_value + 1e-9

    # EV-specific: C feasibility couples SOC residual, charging time, and due window.
    notes = [
        f"clairvoyant={clair:.4f}",
        f"passive={passive_first.value}:{passive_value:.4f}",
        f"dual={dual_first.value}:{dual_value:.4f}",
        f"ce_first={ce_first.value}",
        "exact_within_finite_decision_tree",
        "commitment=A_must_remain_feasible_under_all_prior_theta",
        "optional_C_requires_no_charge_under_tight_due",
        "informative_arc_reveals_theta_perfectly",
        "uninformative_exploit_leaves_posterior=prior",
    ]
    if info_matters:
        notes.append("PHENOMENON: safe dual selects INFORM for optional-C / charge value")
    else:
        notes.append("no_first_action_gap_between_safe_dual_and_safe_passive")

    return DualControlExactReport(
        status=OracleStatus.EXACT,
        clairvoyant_value=clair,
        certainty_equivalent_first=ce_first,
        safe_passive_first=passive_first,
        safe_dual_first=dual_first,
        exact_optimum_first=exact_first,
        safe_passive_value=passive_value,
        safe_dual_value=dual_value,
        exact_value=exact_value,
        dual_differs_from_passive=differs,
        information_changes_first_action=info_matters,
        commitment_safe=True,
        phenomenon_ev_specific=info_matters,
        notes=tuple(notes),
    )


def verify_phenomenon_independent() -> dict:
    """Independent numerical check of the dual-vs-passive gap."""
    report = run_exact_dual_example()
    params = DualToyParams()
    prior = DiscreteBelief.uniform(params.theta_support)

    # Manual: after EXPLOIT, observation e=4 for both theta → posterior=prior.
    # SOC=8. C without charge needs energy 6 (θ=0) or 9 (θ=1). SOC 8 ≥ 6 but not ≥ 9
    # → not safe for all θ → skip C. Value = reward_a - 0.1*4 = 9.6
    passive_manual = params.reward_a - params.energy_cost * 4.0

    # After INFORM: observe 3 → θ=0, SOC=9, C needs 6 → serve C.
    # observe 6 → θ=1, SOC=6, C needs 9 → skip C.
    # Value = 0.5*(10 - 0.1*3 + 5) + 0.5*(10 - 0.1*6) = 0.5*14.7 + 0.5*9.4 = 12.05
    dual_manual = 0.5 * (params.reward_a - params.energy_cost * 3.0 + params.reward_c) + 0.5 * (
        params.reward_a - params.energy_cost * 6.0
    )

    return {
        "report_status": report.status.value,
        "dual_selects_inform": report.safe_dual_first is FirstAction.INFORM,
        "passive_selects_exploit": report.safe_passive_first is FirstAction.EXPLOIT,
        "passive_value_oracle": report.safe_passive_value,
        "passive_value_manual": passive_manual,
        "dual_value_oracle": report.safe_dual_value,
        "dual_value_manual": dual_manual,
        "values_match": (
            report.safe_passive_value is not None
            and report.safe_dual_value is not None
            and abs(report.safe_passive_value - passive_manual) < 1e-9
            and abs(report.safe_dual_value - dual_manual) < 1e-9
        ),
        "information_changes_first_action": report.information_changes_first_action,
        "prior_mean": prior.mean(),
    }
