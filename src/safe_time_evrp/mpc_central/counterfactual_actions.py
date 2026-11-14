"""Counterfactual first-action generator for commitment-preserving MPC.

Constructs distinct, executable first-stage decisions (accept/reject, charge vs
serve, wait vs dispatch, vehicle assignment). ALNS/insertion remain route engines
for suffixes — they are not the paper contribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Decision, Observation, VehicleStatus, Visit


@dataclass(frozen=True)
class FirstActionKey:
    """Canonical executable first decision (not solver name)."""

    newly_accepted: tuple[str, ...]
    rejected: tuple[str, ...]
    first_legs: tuple[tuple[str, str, str], ...]  # (vehicle, node, purpose)

    @staticmethod
    def from_decision(decision: Decision) -> FirstActionKey:
        legs = []
        for vid in sorted(decision.routes):
            visits = decision.routes[vid]
            if visits:
                v0 = visits[0]
                legs.append((vid, v0.node_id, v0.purpose))
            else:
                legs.append((vid, "", "idle"))
        return FirstActionKey(
            newly_accepted=tuple(sorted(decision.newly_accepted)),
            rejected=tuple(sorted(decision.rejected)),
            first_legs=tuple(legs),
        )


@dataclass
class CounterfactualDiagnostics:
    raw_candidates: int = 0
    distinct_first_actions: int = 0
    valid_commitment_safe: int = 0
    selected_key: FirstActionKey | None = None
    keys: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _empty_routes(observation: Observation) -> dict[str, list[Visit]]:
    return {v.id: [] for v in observation.vehicles}


def sanitize_routes(observation: Observation, routes: dict[str, list[Visit]]) -> dict[str, list[Visit]]:
    """Drop service visits that are already completed/rejected or still illegal."""
    banned = set(observation.completed) | set(observation.rejected)
    visible = (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.in_service)
        | set(observation.deferred)
    )
    cleaned: dict[str, list[Visit]] = {}
    for vid, visits in routes.items():
        keep: list[Visit] = []
        for vis in visits:
            if vis.purpose == "service":
                if vis.node_id in banned or vis.node_id not in visible:
                    continue
            keep.append(vis)
        cleaned[vid] = keep
    return cleaned


def _base_decision(observation: Observation, trigger: str, routes, *, newly, rejected, notes) -> Decision:
    accepted = list(observation.accepted)
    for c in newly:
        if c not in accepted:
            accepted.append(c)
    planned = [v.node_id for vs in routes.values() for v in vs if v.purpose == "service"]
    return Decision(
        time=observation.time,
        routes=routes,
        accepted=accepted,
        newly_accepted=list(newly),
        rejected=list(rejected),
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=sorted(set(planned)),
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger=trigger,
        locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
        notes=list(notes),
    )


def _idle_vehicles(observation: Observation) -> list:
    out = []
    for v in observation.vehicles:
        st = v.status if isinstance(v.status, VehicleStatus) else VehicleStatus(v.status)
        if st is VehicleStatus.IDLE and v.locked_destination is None:
            out.append(v)
    return out


def generate_counterfactual_actions(
    instance: Instance,
    observation: Observation,
    *,
    horizon: float,
    energy: NominalLinearEnergy | None = None,
    alns_iterations: int = 12,
    alns_time: float = 0.12,
    seed: int = 0,
    include_solver_baselines: bool = True,
) -> tuple[list[tuple[str, Decision]], CounterfactualDiagnostics]:
    """Return distinct commitment-safe first actions with diagnostics."""
    model = energy or NominalLinearEnergy()
    snapshot = make_public_snapshot(instance, observation, horizon)
    public = snapshot.instance
    diag = CounterfactualDiagnostics()
    raw: list[tuple[str, Decision]] = []

    # --- Solver baselines (optional) ---
    if include_solver_baselines:
        alns = ReactiveAlnsMpc(
            instance, horizon, energy=model, iterations=alns_iterations, time_limit_seconds=alns_time, seed=seed
        )
        ins = EventTriggeredMPC(instance, horizon, model)
        raw.append(("alns", alns.decide(observation, "counterfactual")))
        raw.append(("insertion", ins.decide(observation, "counterfactual")))

    idle = _idle_vehicles(observation)
    announced = [
        c for c in observation.released_open if c not in observation.accepted and c not in observation.rejected
    ]
    chargers = [n.id for n in public.nodes.values() if n.kind is NodeKind.CHARGER]

    # --- Accept vs reject marginal announced customers ---
    for cid in announced[:3]:
        # Reject
        raw.append(
            (
                f"reject:{cid}",
                _base_decision(
                    observation,
                    "cf_reject",
                    _empty_routes(observation),
                    newly=[],
                    rejected=[cid],
                    notes=[f"cf_reject_{cid}"],
                ),
            )
        )
        # Accept on each idle vehicle (single-leg dispatch)
        for veh in idle:
            routes = _empty_routes(observation)
            routes[veh.id] = [Visit(cid, "service")]
            raw.append(
                (
                    f"accept:{cid}@{veh.id}",
                    _base_decision(
                        observation,
                        "cf_accept",
                        routes,
                        newly=[cid],
                        rejected=[c for c in announced if c != cid][:2],
                        notes=[f"cf_accept_{cid}_on_{veh.id}"],
                    ),
                )
            )

    # --- Charge now vs continue (idle vehicles near low SOC or anytime for diversity) ---
    for veh in idle:
        for sid in chargers[:2]:
            routes = _empty_routes(observation)
            routes[veh.id] = [Visit(sid, "charge")]
            raw.append(
                (
                    f"charge:{veh.id}->{sid}",
                    _base_decision(
                        observation,
                        "cf_charge",
                        routes,
                        newly=[],
                        rejected=list(announced[:1]),
                        notes=[f"cf_charge_{veh.id}_{sid}"],
                    ),
                )
            )

    # --- Wait / idle preserve commitments (empty routes) ---
    raw.append(
        (
            "wait_idle",
            _base_decision(
                observation,
                "cf_wait",
                _empty_routes(observation),
                newly=[],
                rejected=list(announced[:1]),
                notes=["cf_wait_idle"],
            ),
        )
    )

    # --- Preserve incumbent commitments only (no new accepts) ---
    if observation.accepted:
        # Best-effort: insertion without new accepts by rejecting announcements
        ins = EventTriggeredMPC(instance, horizon, model)
        base = ins.decide(observation, "cf_commit_only")
        commit = _base_decision(
            observation,
            "cf_commit_only",
            base.routes,
            newly=[],
            rejected=list(announced),
            notes=["cf_commit_only"],
        )
        raw.append(("commit_only", commit))

    diag.raw_candidates = len(raw)

    # Validate + dedupe by FirstActionKey
    seen: dict[FirstActionKey, tuple[str, Decision]] = {}
    for name, cand in raw:
        routes = sanitize_routes(observation, cand.routes)
        newly = [c for c in cand.newly_accepted if c not in observation.completed and c not in observation.rejected]
        newly = [c for c in newly if c in observation.released_open or c in observation.deferred]
        cand = _base_decision(
            observation,
            cand.trigger,
            routes,
            newly=newly,
            rejected=[c for c in cand.rejected if c not in newly],
            notes=list(cand.notes),
        )
        report = validate_continuation(
            public,
            observation,
            cand.routes,
            energy=model,
            require_new=frozenset(cand.newly_accepted),
        )
        if not report.ok:
            # Try stripping new accepts
            if cand.newly_accepted:
                stripped = _base_decision(
                    observation,
                    cand.trigger,
                    cand.routes,
                    newly=[],
                    rejected=list(cand.rejected) + list(cand.newly_accepted),
                    notes=list(cand.notes) + ["stripped_new_accepts"],
                )
                report2 = validate_continuation(public, observation, stripped.routes, energy=model)
                if not report2.ok:
                    continue
                cand = stripped
            else:
                continue
        key = FirstActionKey.from_decision(cand)
        if key not in seen:
            seen[key] = (name, cand)
            diag.keys.append(f"{name}|{key.newly_accepted}|{key.first_legs}")

    diag.distinct_first_actions = len(seen)
    diag.valid_commitment_safe = len(seen)
    diag.notes.append(f"idle_vehicles={len(idle)}")
    diag.notes.append(f"announced={len(announced)}")
    return list(seen.values()), diag
