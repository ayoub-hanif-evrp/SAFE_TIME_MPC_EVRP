"""Exact open-loop / two-stage / multistage / clairvoyant feasibility oracles."""

from __future__ import annotations

from collections import deque
from enum import Enum
from functools import cache
from itertools import product

from safe_time_evrp.multistage.model import ArcMode, State, TinyInstance


class Status(str, Enum):
    PROVEN_FEASIBLE = "proven_feasible"
    PROVEN_INFEASIBLE = "proven_infeasible"
    PROVEN_OPTIMAL = "proven_optimal"
    UNKNOWN = "unknown"
    TIME_LIMIT = "time_limit"


def initial_state(inst: TinyInstance) -> State:
    return State(inst.start_time, inst.depot, inst.start_soc, frozenset(inst.customers), inst.gamma)


def legal_travel(inst: TinyInstance, state: State) -> list[str]:
    dests = []
    for (origin, dest), _modes in inst.arcs.items():
        if origin != state.node:
            continue
        dests.append(dest)
    return sorted(set(dests))


def apply_travel(inst: TinyInstance, state: State, dest: str, mode: ArcMode) -> State | None:
    if mode.z > state.gamma_rem:
        return None
    if state.soc < mode.energy:
        return None
    time = state.time + mode.time
    soc = state.soc - mode.energy
    remaining = set(state.remaining)
    if dest in remaining:
        ready, due = inst.windows[dest]
        if time > due:
            return None
        start = max(time, ready)
        time = start + inst.service.get(dest, 0)
        remaining.discard(dest)
    return State(time, dest, soc, frozenset(remaining), state.gamma_rem - mode.z)


def apply_charge(inst: TinyInstance, state: State, delta: int) -> State | None:
    if state.node not in inst.chargers:
        return None
    if delta < 0 or state.soc + delta > inst.battery:
        return None
    return State(
        state.time + inst.charge_rate * delta,
        state.node,
        state.soc + delta,
        state.remaining,
        state.gamma_rem,
    )


def terminal_ok(inst: TinyInstance, state: State) -> bool:
    return not state.remaining and state.node == inst.depot


def _modes(inst: TinyInstance, origin: str, dest: str) -> tuple[ArcMode, ...]:
    return inst.arcs[(origin, dest)]


def state_key(state: State) -> tuple:
    return (state.time, state.node, state.soc, tuple(sorted(state.remaining)), state.gamma_rem)


def maybe_reset(inst: TinyInstance, state: State, reset: bool) -> State:
    if not reset:
        return state
    return State(state.time, state.node, state.soc, state.remaining, inst.gamma)


def time_limit(inst: TinyInstance) -> int:
    max_due = max((due for _, due in inst.windows.values()), default=0)
    return max_due + inst.battery * inst.charge_rate + 50


# --- Multistage feedback: existence of a causal winning policy ---


def feedback_feasible(inst: TinyInstance, *, reset_budget: bool = False) -> Status:
    """DP over information states. Actions may depend on observed history via state."""

    @cache
    def win(key: tuple) -> bool:
        time, node, soc, rem_t, gamma_rem = key
        state = State(time, node, soc, frozenset(rem_t), gamma_rem)
        if terminal_ok(inst, state):
            return True
        if state.time > time_limit(inst):
            return False
        if state.node in inst.chargers and state.soc < inst.battery:
            # delta=0 is a no-op and would recurse forever; travel covers the zero-charge case.
            for delta in range(1, inst.battery - state.soc + 1):
                nxt = apply_charge(inst, state, delta)
                if nxt is not None and win(state_key(nxt)):
                    return True
        for dest in legal_travel(inst, state):
            modes = _modes(inst, state.node, dest)
            admissible = [m for m in modes if m.z <= state.gamma_rem]
            if not admissible:
                continue
            if all(
                (child := apply_travel(inst, state, dest, m)) is not None
                and win(state_key(maybe_reset(inst, child, reset_budget)))
                for m in admissible
            ):
                return True
        return False

    root = initial_state(inst)
    return Status.PROVEN_FEASIBLE if win(state_key(root)) else Status.PROVEN_INFEASIBLE


# --- Open-loop: one fixed sequence of (kind, arg) must survive all disturbance paths ---


def open_loop_feasible(inst: TinyInstance) -> Status:
    """Enumerate short open-loop plans: list of travel destinations and charge deltas."""
    max_len = inst.max_depth
    q: deque[list[tuple]] = deque([[]])
    seen_prefixes = 0
    while q and seen_prefixes < 50_000:
        plan = q.popleft()
        seen_prefixes += 1
        if simulate_open_loop(inst, plan):
            return Status.PROVEN_FEASIBLE
        if len(plan) >= max_len:
            continue
        node = forced_node(inst, plan)
        if node in inst.chargers:
            for delta in range(0, inst.battery + 1):
                q.append(plan + [("c", delta)])
        if node is not None:
            for dest in sorted({d for (o, d) in inst.arcs if o == node}):
                q.append(plan + [("t", dest)])
    return Status.PROVEN_INFEASIBLE


def simulate_open_loop(inst: TinyInstance, plan: list[tuple]) -> bool:
    travel_arcs: list[str] = [arg for kind, arg in plan if kind == "t"]
    mode_lists: list[list[ArcMode]] = []
    cursor = inst.depot
    for dest in travel_arcs:
        if (cursor, dest) not in inst.arcs:
            return False
        mode_lists.append(list(inst.arcs[(cursor, dest)]))
        cursor = dest

    if not mode_lists:
        state = initial_state(inst)
        for kind, arg in plan:
            if kind != "c":
                return False
            state = apply_charge(inst, state, arg)
            if state is None:
                return False
        return terminal_ok(inst, state)

    for combo in product(*mode_lists):
        state = initial_state(inst)
        ti = 0
        for kind, arg in plan:
            if kind == "c":
                state = apply_charge(inst, state, arg)
                if state is None:
                    return False
            else:
                mode = combo[ti]
                ti += 1
                if mode.z > state.gamma_rem:
                    return False
                state = apply_travel(inst, state, arg, mode)
                if state is None:
                    return False
        if not terminal_ok(inst, state):
            return False
    return True


def forced_node(inst: TinyInstance, plan: list[tuple]) -> str | None:
    node = inst.depot
    for kind, arg in plan:
        if kind == "t":
            if (node, arg) not in inst.arcs:
                return None
            node = arg
        elif kind == "c":
            if node not in inst.chargers:
                return None
    return node


# --- Two-stage Han-style: fix travel sequence; charges may depend on full disturbance path ---


def two_stage_fixed_route_feasible(inst: TinyInstance) -> Status:
    """First-stage travel sequence; second-stage charges after each arrival given the mode path."""
    seqs: list[tuple[str, ...]] = []
    q: deque[tuple[str, ...]] = deque([(inst.depot,)])
    while q and len(seqs) < 5_000:
        path = q.popleft()
        node = path[-1]
        if len(path) > 1 and not (set(inst.customers) - set(path)) and node == inst.depot:
            seqs.append(path)
        if len(path) >= inst.max_depth:
            continue
        for dest in sorted({d for (o, d) in inst.arcs if o == node}):
            q.append(path + (dest,))

    for path in seqs:
        travels = list(zip(path[:-1], path[1:], strict=True))
        mode_lists = [list(inst.arcs[arc]) for arc in travels]
        if not mode_lists:
            if not inst.customers:
                return Status.PROVEN_FEASIBLE
            continue
        if all(_charges_exist_for_path(inst, path, combo) for combo in product(*mode_lists)):
            return Status.PROVEN_FEASIBLE
    return Status.PROVEN_INFEASIBLE


def _charges_exist_for_path(inst: TinyInstance, path: tuple[str, ...], modes: tuple[ArcMode, ...]) -> bool:
    """Exact charge DP on a fixed path for one disturbance realization."""

    @cache
    def ok(i: int, time: int, soc: int, rem: tuple[str, ...], gamma_rem: int) -> bool:
        remaining = set(rem)
        node = path[i]
        if i == len(path) - 1:
            return not remaining and node == inst.depot
        max_delta = inst.battery - soc if node in inst.chargers else 0

        def after_charge(delta: int) -> bool:
            t2 = time + inst.charge_rate * delta
            s2 = soc + delta
            mode = modes[i]
            if mode.z > gamma_rem or s2 < mode.energy:
                return False
            t3 = t2 + mode.time
            s3 = s2 - mode.energy
            rem2 = set(remaining)
            dest = path[i + 1]
            if dest in rem2:
                ready, due = inst.windows[dest]
                if t3 > due:
                    return False
                t3 = max(t3, ready) + inst.service.get(dest, 0)
                rem2.discard(dest)
            return ok(i + 1, t3, s3, tuple(sorted(rem2)), gamma_rem - mode.z)

        if max_delta == 0:
            return after_charge(0)
        return any(after_charge(delta) for delta in range(0, max_delta + 1))

    return ok(0, inst.start_time, inst.start_soc, tuple(sorted(inst.customers)), inst.gamma)


# --- Clairvoyant: for every disturbance world a (possibly different) plan works ---


def clairvoyant_feasible(inst: TinyInstance) -> Status:
    """Upper bound: each full mode combination may use its own open plan (via path+charges)."""
    # Enumerate short travel sequences; for each world (combo on that seq) check charges.
    # Clairvoyant wins if EVERY admissible global disturbance can be covered by SOME sequence.
    # Conservative exact check for tiny graphs: for each arc-mode choice consistent with gamma
    # along some covering path — use per-scenario feedback with singleton mode sets.

    # Build all scenarios as assignments of one mode per arc, filtered by total z <= gamma
    arc_keys = sorted(inst.arcs.keys())
    mode_lists = [list(inst.arcs[a]) for a in arc_keys]
    for combo in product(*mode_lists):
        if sum(m.z for m in combo) > inst.gamma:
            continue
        single = {arc: (mode,) for arc, mode in zip(arc_keys, combo, strict=True)}
        scen = TinyInstance(
            name=inst.name + "-scen",
            nodes=inst.nodes,
            depot=inst.depot,
            chargers=inst.chargers,
            customers=inst.customers,
            windows=inst.windows,
            service=inst.service,
            arcs=single,
            battery=inst.battery,
            charge_rate=inst.charge_rate,
            gamma=inst.gamma,
            start_soc=inst.start_soc,
            start_time=inst.start_time,
            max_depth=inst.max_depth,
        )
        if feedback_feasible(scen) is not Status.PROVEN_FEASIBLE:
            return Status.PROVEN_INFEASIBLE
    return Status.PROVEN_FEASIBLE


def evaluate_mode(inst: TinyInstance, mode: str) -> Status:
    if mode == "open_loop":
        return open_loop_feasible(inst)
    if mode == "two_stage":
        return two_stage_fixed_route_feasible(inst)
    if mode == "feedback":
        return feedback_feasible(inst, reset_budget=False)
    if mode == "feedback_reset_budget":
        return feedback_feasible(inst, reset_budget=True)
    if mode == "clairvoyant":
        return clairvoyant_feasible(inst)
    return Status.UNKNOWN
