"""Observation-timing upper bound (OTUB) for decision-relevant dual MPC.

Declared model (single-EV corridor family, same as REUB_v1):
  customers {A,C}, charger S, first action = D→A corridor with observation time
  τ_obs = travel_time(corridor). No operational decisions occur before τ_obs
  except the first travel itself (already fixed when evaluating Q(a)).

Construction
------------
After completing a under θ, the posterior support S_θ is known at τ_obs.
Continuation decisions (serve A; direct vs charge-then-C) occur at t ≥ τ_obs.

OTUB uses:
  - exact first-action expected travel reward E[r_travel(a,θ)]
  - post-observation optimistic resource envelope that **respects information sets**:
      * if |S|=1: count optional C if reachable under that θ (optimistic mins = exact energies)
      * if |S|>1: count C only if there exists ONE route pattern (direct OR charge-then-C)
        that is optimistic-feasible under EVERY θ in S (common pre-separation decision)

Claim (family-restricted): Q*(a) ≤ OTUB(a).

Relation to DRUB: OTUB ≤ DRUB is a **research goal**, not automatic. On uninformative
corridors, DRUB allows θ-contingent OL while OTUB forces a common pattern for C,
so OTUB can be strictly tighter. On fully informative corridors with Dirac posteriors,
OTUB matches the resource/OL envelope per θ and typically equals DRUB for this family.

Status: VALID_FAMILY_BOUND for the declared single-EV {A,C,S} model; returns
UNSUPPORTED_BOUND outside that model.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.bound_result import BoundStatus
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action


@dataclass(frozen=True)
class TimingBoundResult:
    status: BoundStatus
    value: float | None
    tau_obs: float | None
    notes: tuple[str, ...]


def _family_segments(net: RoadNetwork):
    try:
        ac = next(s for s in net.segments if s.segment_id == "AC")
        as_ = next(s for s in net.segments if s.segment_id == "AS")
        sa = next(s for s in net.segments if s.segment_id == "SA")
        ch = net.chargers[0]
        _ = net.customer("cust_A")
        _ = net.customer("cust_C")
        return ac, as_, sa, ch
    except (StopIteration, IndexError, KeyError):
        return None


def _c_reachable_direct(net: RoadNetwork, soc: float, t: float, theta: float, ac) -> bool:
    cust_c = net.customer("cust_C")
    if net.energy(ac, theta) > soc + 1e-12:
        return False
    t_c = t + ac.travel_time
    return max(t_c, cust_c.ready) + cust_c.service_time <= cust_c.due + 1e-12


def _c_reachable_charge(net: RoadNetwork, soc: float, t: float, theta: float, as_, sa, ch, ac) -> bool:
    e_as = net.energy(as_, theta)
    if e_as > soc + 1e-12:
        return False
    t1 = t + as_.travel_time
    soc1 = soc - e_as
    deficit = net.battery - soc1
    t_chg = ch.full_charge_time * (deficit / net.battery)
    t2 = t1 + t_chg
    e_sa = net.energy(sa, theta)
    if e_sa > net.battery + 1e-12:
        return False
    t3 = t2 + sa.travel_time
    soc3 = net.battery - e_sa
    return _c_reachable_direct(net, soc3, t3, theta, ac)


def _post_obs_envelope(
    net: RoadNetwork,
    soc: float,
    t: float,
    support: frozenset[float],
    ac,
    as_,
    sa,
    ch,
) -> float:
    """Optimistic continuation reward after observation (A assumed served if needed)."""
    reward = 0.0
    cust_a = net.customer("cust_A")
    # Serve A if present (always at node A in this family after first travel)
    start = max(t, cust_a.ready)
    if start + cust_a.service_time > cust_a.due + 1e-12:
        return float("-inf")
    reward += cust_a.reward
    t_a = start + cust_a.service_time
    cust_c = net.customer("cust_C")

    if len(support) <= 1:
        th = next(iter(support))
        if _c_reachable_direct(net, soc, t_a, th, ac) or _c_reachable_charge(net, soc, t_a, th, as_, sa, ch, ac):
            reward += cust_c.reward
        return reward

    # Ambiguous information set: common pattern required
    direct_ok_all = all(_c_reachable_direct(net, soc, t_a, th, ac) for th in support)
    charge_ok_all = all(_c_reachable_charge(net, soc, t_a, th, as_, sa, ch, ac) for th in support)
    if direct_ok_all or charge_ok_all:
        reward += cust_c.reward
    return reward


def evaluate_observation_timing_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> TimingBoundResult:
    """OTUB: Q* ≤ OTUB; may be ≤ DRUB on uninformative actions (goal, verified empirically)."""
    COUNTERS.bound_evaluations += 1  # count as bound construction
    fam = _family_segments(net)
    if fam is None or action.segment_id is None:
        return TimingBoundResult(BoundStatus.UNSUPPORTED_BOUND, None, None, ("not_AC_S_family",))
    ac, as_, sa, ch = fam
    try:
        seg = next(s for s in net.segments if s.segment_id == action.segment_id)
    except StopIteration:
        return TimingBoundResult(BoundStatus.UNSUPPORTED_BOUND, None, None, ("unknown_segment",))

    tau_obs = seg.travel_time
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if tr.state is None or (not tr.ok and not tr.model_inconsistent):
            return TimingBoundResult(BoundStatus.PROVEN_INFEASIBLE, None, tau_obs, ("first_action_infeasible",))
        if tr.model_inconsistent:
            return TimingBoundResult(BoundStatus.PROVEN_INFEASIBLE, None, tau_obs, ("model_inconsistent",))
        v = tr.state.vehicle(action.vehicle_id)
        support = tr.state.belief.support_set()
        cont = _post_obs_envelope(net, v.soc, v.time, support, ac, as_, sa, ch)
        if cont < -1e8:
            return TimingBoundResult(BoundStatus.PROVEN_INFEASIBLE, None, tau_obs, ("cannot_serve_A",))
        total += p * (tr.reward_delta + cont)

    return TimingBoundResult(
        BoundStatus.VALID_BOUND,
        total,
        tau_obs,
        (
            "OTUB_family_restricted",
            "pre_obs_decisions=none_besides_first_travel",
            "post_obs_common_pattern_if_ambiguous",
        ),
    )


def otub_vs_clairvoyant_on_action(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
) -> dict:
    from safe_time_evrp.dr_dual.bounds import evaluate_clairvoyant_bound
    from safe_time_evrp.dr_dual.exact_oracle import _bayes_value_after_first

    ot = evaluate_observation_timing_bound(net, state, action)
    dr = evaluate_clairvoyant_bound(net, state, action)
    q = _bayes_value_after_first(net, state, action, mode="safe_dual")
    return {
        "action": action.key(),
        "otub_status": ot.status.value,
        "otub": ot.value,
        "drub": dr,
        "q_star": q,
        "otub_ge_q": ot.value is not None and q is not None and ot.value + 1e-9 >= q,
        "otub_le_drub": ot.value is not None and dr is not None and ot.value <= dr + 1e-9,
        "tau_obs": ot.tau_obs,
    }
