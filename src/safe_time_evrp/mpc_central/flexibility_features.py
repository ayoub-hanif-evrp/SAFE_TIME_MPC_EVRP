"""Lightweight fleet-flexibility features for candidate screening.

Features are interpretable and use only public observation + nominal routes.
Coefficients, when used, must be fit on train/development only.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.state import Decision, Observation


@dataclass(frozen=True)
class FlexibilitySnapshot:
    mean_battery: float
    min_battery: float
    n_idle_at_depot: int
    n_busy: int
    accepted_open: int
    released_open: int
    route_stops: int
    charge_legs: int
    wait_legs: int
    service_legs: int


def flexibility_snapshot(observation: Observation, decision: Decision | None = None) -> FlexibilitySnapshot:
    bats = [float(v.soc) for v in observation.vehicles]
    idle = sum(1 for v in observation.vehicles if str(getattr(v.status, "value", v.status)) == "idle")
    busy = len(observation.vehicles) - idle
    routes = decision.routes if decision is not None else {}
    stops = sum(len(vs) for vs in routes.values())
    charge = sum(1 for vs in routes.values() for v in vs if v.purpose == "charge")
    wait = sum(1 for vs in routes.values() for v in vs if v.purpose == "wait")
    service = sum(1 for vs in routes.values() for v in vs if v.purpose == "service")
    return FlexibilitySnapshot(
        mean_battery=(sum(bats) / len(bats)) if bats else 0.0,
        min_battery=min(bats) if bats else 0.0,
        n_idle_at_depot=idle,
        n_busy=busy,
        accepted_open=len(observation.accepted),
        released_open=len(observation.released_open),
        route_stops=stops,
        charge_legs=charge,
        wait_legs=wait,
        service_legs=service,
    )


def cheap_terminal_bonus(
    snapshot: FlexibilitySnapshot,
    *,
    expected_remaining: float,
    w_battery: float = 0.02,
    w_idle: float = 0.15,
    w_remain: float = 0.05,
) -> float:
    """Tiny additive bonus for ranking near-ties — not a service reward for waiting.

    Scaled small so it cannot override large causal value gaps; used only for
    screening / tie-breaks when expected_remaining > 0.
    """
    if expected_remaining <= 1e-9:
        return 0.0
    return (
        w_battery * snapshot.min_battery
        + w_idle * float(snapshot.n_idle_at_depot)
        + w_remain * min(expected_remaining, 5.0) * (1.0 if snapshot.min_battery > 5.0 else 0.0)
    )


def prioritize_candidates_for_rollout(
    named: list[tuple[str, Decision]],
    observation: Observation,
    *,
    expected_remaining: float,
    max_keep: int = 6,
) -> list[tuple[str, Decision]]:
    """Keep incumbent-like and diversity of serve/charge/wait/reject under a cap."""
    if len(named) <= max_keep:
        return list(named)

    def score(item: tuple[str, Decision]) -> float:
        name, cand = item
        snap = flexibility_snapshot(observation, cand)
        bonus = cheap_terminal_bonus(snap, expected_remaining=expected_remaining)
        # Prefer named diversity tags.
        tag = 0.0
        if "incumbent" in name or "greedy" in name or name.endswith("_nominal"):
            tag += 5.0
        if "charge" in name:
            tag += 1.5 if expected_remaining > 0 else 0.2
        if "wait" in name:
            tag += 0.5 if expected_remaining > 0 else -0.5
        if "reject" in name or "defer" in name:
            tag += 1.0 if expected_remaining > 0.5 else 0.0
        if "accept" in name or "service" in name or "insert" in name:
            tag += 1.2
        return tag + bonus + 0.01 * len(cand.newly_accepted)

    ranked = sorted(named, key=score, reverse=True)
    return ranked[:max_keep]
