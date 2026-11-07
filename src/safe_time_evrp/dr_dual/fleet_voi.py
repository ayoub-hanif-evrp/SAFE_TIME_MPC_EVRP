"""Isolate cross-vehicle information value from EV1 travel geometry/cost.

Controlled comparison: identical EV1 physical first action and identical true θ,
EV2 either (i) receives the completed energy observation (shared posterior) or
(ii) must act under the forced prior. Difference = fleet information value.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.fleet_oracle import Ev2Action, _realize_ev2, _sync_wait
from safe_time_evrp.dr_dual.network import (
    ChargerSpec,
    CustomerSpec,
    RoadNetwork,
    Segment,
    make_two_ev_shared_theta,
)
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def make_two_ev_zero_voi_baseline() -> RoadNetwork:
    """Legacy toy: charge weakly dominates direct → sharing changes labels, not value."""
    return make_two_ev_shared_theta()


def make_two_ev_positive_voi() -> RoadNetwork:
    """Tight battery + costly charge detour: θ decides DIRECT vs CHARGE with strict reward gap.

    Battery 8. Direct energy = 5+4θ → feasible only for θ=0.
    Charge path travel energy higher for θ=0 than direct, so with info θ=0 prefers DIRECT.
    Without info, only CHARGE (or SKIP) is robustly feasible → VoI > 0.
    """
    segs = (
        Segment("E1_exploit", "D1", "A1", travel_time=8.0, base_energy=3.0, informative=0.0),
        Segment("E1_inform", "D1", "A1", travel_time=10.0, base_energy=2.0, informative=4.0),
        Segment("A1_S1", "A1", "S1", travel_time=1.0, base_energy=0.4, informative=0.0),
        Segment("E2_to_B", "D2", "B", travel_time=9.0, base_energy=5.0, informative=4.0),  # 5 or 9
        Segment("D2_S2", "D2", "S2", travel_time=2.0, base_energy=1.0, informative=0.0),
        Segment("S2_B", "S2", "B", travel_time=7.0, base_energy=4.5, informative=1.5),  # 4.5 or 6
    )
    return RoadNetwork(
        name="dr_two_ev_positive_voi",
        nodes=("D1", "A1", "S1", "D2", "S2", "B"),
        depot="D1",
        battery=8.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A1", "A1", ready=0.0, due=80.0, service_time=1.0, reward=10.0),
            CustomerSpec("cust_B", "B", ready=12.0, due=40.0, service_time=1.0, reward=6.0),
        ),
        chargers=(
            ChargerSpec("chg_S1", "S1", full_charge_time=12.0),
            ChargerSpec("chg_S2", "S2", full_charge_time=4.0),  # fast enough to meet due after charge
        ),
        energy_cost=0.5,  # amplify travel-energy gap so DIRECT≻CHARGE under θ=0 is economically clear
        metadata={
            "accepted_init": ("cust_A1",),
            "optional": ("cust_B",),
            "vehicles": ("v1", "v2"),
            "start_nodes": {"v1": "D1", "v2": "D2"},
        },
    )


def _run_ev1(
    net: RoadNetwork,
    state0: WorldState,
    first: Action,
    theta: float,
) -> tuple[WorldState, float, float] | None:
    tr = apply_action(net, state0, first, theta_star=theta)
    if not tr.ok or tr.state is None:
        return None
    t_obs = tr.state.vehicle("v1").time
    tr2 = apply_action(net, tr.state, Action(ActionKind.SERVE, "v1", customer_id="cust_A1"), theta_star=theta)
    if not tr2.ok or tr2.state is None:
        return None
    s = _sync_wait(net, tr2.state, "v2", t_obs, theta)
    if s is None:
        return None
    return s, tr.reward_delta + tr2.reward_delta, t_obs


def _best_ev2_common(
    net: RoadNetwork,
    branches: list[tuple[float, float, WorldState]],
    *,
    force_prior_belief: bool,
) -> tuple[float, Ev2Action, dict[float, float]]:
    """One common EV2 action maximizing expected reward over branches."""
    best_act = Ev2Action.SKIP
    best_score = float("-inf")
    best_per: dict[float, float] = {}
    z = sum(p for _, p, _ in branches)
    for act in (Ev2Action.DIRECT, Ev2Action.CHARGE, Ev2Action.SKIP):
        scores = []
        per: dict[float, float] = {}
        feasible = True
        for th, p, st in branches:
            st_use = st
            if force_prior_belief:
                st_use = WorldState(
                    st.vehicles,
                    st.accepted,
                    st.completed,
                    st.rejected,
                    st.announced,
                    DiscreteBelief.uniform(net.theta_support),
                    st.stage,
                )
            r = _realize_ev2(net, st_use, act, th, info_available=not force_prior_belief)
            if r is None and act is not Ev2Action.SKIP:
                feasible = False
                break
            rv = 0.0 if r is None else r
            per[th] = rv
            scores.append((p / z) * rv)
        if not feasible:
            continue
        score = sum(scores)
        if score > best_score:
            best_score = score
            best_act = act
            best_per = per
    return best_score, best_act, best_per


def _best_ev2_contingent(
    net: RoadNetwork,
    branches: list[tuple[float, float, WorldState]],
) -> tuple[float, dict[float, Ev2Action], dict[float, float]]:
    """Per-θ EV2 action (only valid when each branch has Dirac / separated history)."""
    policy: dict[float, Ev2Action] = {}
    per: dict[float, float] = {}
    total = 0.0
    for th, p, st in branches:
        best_a = Ev2Action.SKIP
        best_r = 0.0
        for act in (Ev2Action.DIRECT, Ev2Action.CHARGE, Ev2Action.SKIP):
            r = _realize_ev2(net, st, act, th, info_available=True)
            if r is None and act is not Ev2Action.SKIP:
                continue
            rv = 0.0 if r is None else r
            if rv >= best_r:
                best_r = rv
                best_a = act
        policy[th] = best_a
        per[th] = best_r
        total += p * best_r
    return total, policy, per


@dataclass(frozen=True)
class FleetVoIResult:
    network: str
    ev1_action: str
    v_shared: float
    v_without_sharing: float
    delta_voi: float
    shared_policy: dict
    no_share_policy: str
    per_theta_shared: dict
    per_theta_no_share: dict
    notes: tuple[str, ...]


def measure_fleet_information_value(
    net: RoadNetwork | None = None,
    *,
    ev1_segment: str = "E1_inform",
) -> FleetVoIResult:
    """Hold EV1 action fixed; compare EV2 with vs without receiving the observation."""
    from safe_time_evrp.dr_dual.exact_oracle import initial_state_two

    net = net or make_two_ev_shared_theta()
    state0 = initial_state_two(net)
    first = Action(ActionKind.TRAVEL, "v1", segment_id=ev1_segment)
    branches: list[tuple[float, float, WorldState]] = []
    for th, p in zip(state0.belief.support, state0.belief.probs, strict=True):
        if p <= 0:
            continue
        out = _run_ev1(net, state0, first, th)
        if out is None:
            continue
        s, _ev1_r, _t = out
        branches.append((th, p, s))

    # Shared: if informative, histories separate → contingent; else common on posterior
    informative = abs(next(s for s in net.segments if s.segment_id == ev1_segment).informative) > 1e-12
    if informative and all(len(st.belief.support_set()) <= 1 for _, _, st in branches):
        v_shared, pol_map, per_s = _best_ev2_contingent(net, branches)
        shared_policy = {str(k): v.value for k, v in pol_map.items()}
    else:
        v_shared, act, per_s = _best_ev2_common(net, branches, force_prior_belief=False)
        shared_policy = {"common": act.value}

    v_no, act_no, per_n = _best_ev2_common(net, branches, force_prior_belief=True)
    delta = v_shared - v_no
    notes = []
    if abs(delta) < 1e-9:
        notes.append("delta_voi≈0: sharing does not improve EV2 expected reward")
    else:
        notes.append("delta_voi>0: sharing strictly improves EV2 expected reward")
    # Dominance diagnostics for legacy network
    notes.append("compare_route_energies: inspect Segment E2_to_B vs D2_S2+S2_B under each θ")
    return FleetVoIResult(
        network=net.name,
        ev1_action=first.key(),
        v_shared=v_shared,
        v_without_sharing=v_no,
        delta_voi=delta,
        shared_policy=shared_policy,
        no_share_policy=act_no.value,
        per_theta_shared={str(k): v for k, v in per_s.items()},
        per_theta_no_share={str(k): v for k, v in per_n.items()},
        notes=tuple(notes),
    )


def decompose_legacy_zero_voi() -> dict:
    """Explicit numerical decomposition for the original two-EV network."""
    net = make_two_ev_shared_theta()
    # Energies
    direct = {th: net.energy(next(s for s in net.segments if s.segment_id == "E2_to_B"), th) for th in (0.0, 1.0)}
    via = {
        th: net.energy(next(s for s in net.segments if s.segment_id == "D2_S2"), th)
        + net.energy(next(s for s in net.segments if s.segment_id == "S2_B"), th)
        for th in (0.0, 1.0)
    }
    voi = measure_fleet_information_value(net, ev1_segment="E1_inform")
    return {
        "direct_energy": direct,
        "charge_route_travel_energy": via,
        "battery": net.battery,
        "charge_weakly_dominates_travel_energy": all(via[th] <= direct[th] + 1e-12 for th in (0.0, 1.0)),
        "both_feasible_under_battery": all(direct[th] <= net.battery and via[th] <= net.battery for th in (0.0, 1.0)),
        "fleet_voi": {
            "v_shared": voi.v_shared,
            "v_without_sharing": voi.v_without_sharing,
            "delta": voi.delta_voi,
            "shared_policy": voi.shared_policy,
            "no_share_policy": voi.no_share_policy,
        },
        "conclusion": "zero_or_negligible_fleet_VoI_on_legacy_network",
    }
