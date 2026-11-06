"""True multi-stage receding-horizon controller on the discrete toy plant (Gate D)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import cache
from itertools import product

from safe_time_evrp.multistage.certificate import terminal_viability_certificate
from safe_time_evrp.multistage.model import ArcMode, State, TinyInstance
from safe_time_evrp.multistage.oracle import (
    Status,
    apply_charge,
    apply_travel,
    evaluate_mode,
    forced_node,
    initial_state,
    legal_travel,
    simulate_open_loop,
    state_key,
    terminal_ok,
    time_limit,
    two_stage_fixed_route_feasible,
)


@dataclass
class StepRecord:
    time: int
    node: str
    soc: int
    gamma_rem: int
    action: str
    mode_name: str | None = None


@dataclass
class RunResult:
    controller: str
    success: bool
    steps: list[StepRecord]
    note: str = ""


def _admissible(inst: TinyInstance, state: State, dest: str) -> list[ArcMode]:
    return [m for m in inst.arcs[(state.node, dest)] if m.z <= state.gamma_rem]


def _feedback_from_state(inst: TinyInstance, state: State) -> Status:
    """Exact causal feasibility from an arbitrary information state."""

    @cache
    def win(key: tuple) -> bool:
        time, node, soc, rem_t, gamma_rem = key
        st = State(time, node, soc, frozenset(rem_t), gamma_rem)
        if terminal_ok(inst, st):
            return True
        if st.time > time_limit(inst):
            return False
        if st.node in inst.chargers and st.soc < inst.battery:
            for delta in range(1, inst.battery - st.soc + 1):
                nxt = apply_charge(inst, st, delta)
                if nxt is not None and win(state_key(nxt)):
                    return True
        for dest in legal_travel(inst, st):
            adm = [m for m in inst.arcs[(st.node, dest)] if m.z <= st.gamma_rem]
            if not adm:
                continue
            if all(
                (child := apply_travel(inst, st, dest, m)) is not None and win(state_key(child))
                for m in adm
            ):
                return True
        return False

    return Status.PROVEN_FEASIBLE if win(state_key(state)) else Status.PROVEN_INFEASIBLE


def _pick_feedback_action_exact(inst: TinyInstance, state: State) -> tuple[str, object] | None:
    if terminal_ok(inst, state):
        return None
    if state.node in inst.chargers and state.soc < inst.battery:
        for delta in range(1, inst.battery - state.soc + 1):
            nxt = apply_charge(inst, state, delta)
            if nxt is not None and _feedback_from_state(inst, nxt) is Status.PROVEN_FEASIBLE:
                return ("charge", delta)
    for dest in legal_travel(inst, state):
        adm = _admissible(inst, state, dest)
        if not adm:
            continue
        if all(
            (child := apply_travel(inst, state, dest, m)) is not None
            and _feedback_from_state(inst, child) is Status.PROVEN_FEASIBLE
            for m in adm
        ):
            return ("travel", dest)
    return None


def _open_loop_plan(inst: TinyInstance) -> list[tuple] | None:
    q: deque[list[tuple]] = deque([[]])
    seen = 0
    while q and seen < 50_000:
        plan = q.popleft()
        seen += 1
        if simulate_open_loop(inst, plan):
            return plan
        if len(plan) >= inst.max_depth:
            continue
        node = forced_node(inst, plan)
        if node in inst.chargers:
            for delta in range(0, inst.battery + 1):
                q.append(plan + [("c", delta)])
        if node is not None:
            for dest in sorted({d for (o, d) in inst.arcs if o == node}):
                q.append(plan + [("t", dest)])
    return None


def _open_loop_plan_return_to(inst: TinyInstance, state: State) -> list[tuple] | None:
    """Open-loop plan from an arbitrary state returning to inst.depot."""

    def simulate(plan: list[tuple]) -> bool:
        travel_dests = [arg for k, arg in plan if k == "t"]
        mode_lists = []
        cursor = state.node
        for dest in travel_dests:
            if (cursor, dest) not in inst.arcs:
                return False
            mode_lists.append(list(inst.arcs[(cursor, dest)]))
            cursor = dest
        combos = list(product(*mode_lists)) if mode_lists else [()]
        for combo in combos:
            st = state
            ti = 0
            for kind, arg in plan:
                if kind == "c":
                    st = apply_charge(inst, st, arg)
                    if st is None:
                        return False
                else:
                    mode = combo[ti]
                    ti += 1
                    if mode.z > st.gamma_rem:
                        return False
                    st = apply_travel(inst, st, arg, mode)
                    if st is None:
                        return False
            if not terminal_ok(inst, st):
                return False
        return True

    q: deque[list[tuple]] = deque([[]])
    seen = 0
    while q and seen < 20_000:
        plan = q.popleft()
        seen += 1
        if plan and simulate(plan):
            return plan
        if len(plan) >= inst.max_depth:
            continue
        node = state.node
        for kind, arg in plan:
            if kind == "t":
                node = arg
        if node in inst.chargers:
            for delta in range(0, inst.battery + 1):
                q.append(plan + [("c", delta)])
        for dest in sorted({d for (o, d) in inst.arcs if o == node}):
            q.append(plan + [("t", dest)])
    return None


def run_open_loop(inst: TinyInstance, scenario: dict[tuple[str, str], ArcMode]) -> RunResult:
    plan = _open_loop_plan(inst)
    steps: list[StepRecord] = []
    if plan is None:
        return RunResult("open_loop", False, steps, note="no open-loop plan")
    state = initial_state(inst)
    for kind, arg in plan:
        if kind == "c":
            nxt = apply_charge(inst, state, arg)
            if nxt is None:
                return RunResult("open_loop", False, steps, note="charge failed")
            steps.append(StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"charge:{arg}"))
            state = nxt
        else:
            mode = scenario.get((state.node, arg))
            if mode is None:
                modes = inst.arcs[(state.node, arg)]
                mode = next((m for m in modes if m.z <= state.gamma_rem), modes[0])
            nxt = apply_travel(inst, state, arg, mode)
            steps.append(
                StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"travel:{arg}", mode.name)
            )
            if nxt is None:
                return RunResult("open_loop", False, steps, note="travel failed")
            state = nxt
    return RunResult("open_loop", terminal_ok(inst, state), steps)


def run_feedback_mpc(inst: TinyInstance, scenario: dict[tuple[str, str], ArcMode]) -> RunResult:
    """Receding-horizon: at each state re-solve exact multistage feasibility and apply one action."""
    state = initial_state(inst)
    steps: list[StepRecord] = []
    for _ in range(inst.max_depth * 3):
        if terminal_ok(inst, state):
            return RunResult("feedback_mpc", True, steps)
        action = _pick_feedback_action_exact(inst, state)
        if action is None:
            return RunResult("feedback_mpc", False, steps, note="no winning action")
        kind, arg = action
        if kind == "charge":
            steps.append(StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"charge:{arg}"))
            nxt = apply_charge(inst, state, int(arg))
            if nxt is None:
                return RunResult("feedback_mpc", False, steps, note="charge failed")
            state = nxt
        else:
            dest = str(arg)
            mode = scenario.get((state.node, dest))
            if mode is None:
                modes = _admissible(inst, state, dest)
                if not modes:
                    return RunResult("feedback_mpc", False, steps, note="no admissible mode")
                mode = modes[0]
            steps.append(
                StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"travel:{dest}", mode.name)
            )
            nxt = apply_travel(inst, state, dest, mode)
            if nxt is None:
                return RunResult("feedback_mpc", False, steps, note="travel failed")
            state = nxt
    return RunResult("feedback_mpc", terminal_ok(inst, state), steps, note="horizon exhausted")


def run_two_stage_then_execute(inst: TinyInstance, scenario: dict[tuple[str, str], ArcMode]) -> RunResult:
    """Execute a Han-style fixed route with scenario modes and adaptive charges if one exists."""
    if two_stage_fixed_route_feasible(inst) is not Status.PROVEN_FEASIBLE:
        return RunResult("two_stage", False, [], note="no fixed-route two-stage policy")

    q: deque[tuple[str, ...]] = deque([(inst.depot,)])
    while q:
        path = q.popleft()
        node = path[-1]
        if len(path) > 1 and not (set(inst.customers) - set(path)) and node == inst.depot:
            modes = []
            for arc in zip(path[:-1], path[1:], strict=True):
                if arc in scenario:
                    modes.append(scenario[arc])
                else:
                    modes.append(min(inst.arcs[arc], key=lambda m: m.z))
            state = initial_state(inst)
            steps: list[StepRecord] = []
            ok = True
            for i, dest in enumerate(path[1:]):
                if state.node in inst.chargers:
                    charged = False
                    for delta in range(0, inst.battery - state.soc + 1):
                        trial = state if delta == 0 else apply_charge(inst, state, delta)
                        if trial is None:
                            continue
                        nxt = apply_travel(inst, trial, dest, modes[i])
                        if nxt is not None:
                            if delta:
                                steps.append(
                                    StepRecord(
                                        state.time, state.node, state.soc, state.gamma_rem, f"charge:{delta}"
                                    )
                                )
                            state = trial
                            charged = True
                            break
                    if not charged:
                        ok = False
                        break
                mode = modes[i]
                steps.append(
                    StepRecord(
                        state.time, state.node, state.soc, state.gamma_rem, f"travel:{dest}", mode.name
                    )
                )
                nxt = apply_travel(inst, state, dest, mode)
                if nxt is None:
                    ok = False
                    break
                state = nxt
            if ok and terminal_ok(inst, state):
                return RunResult("two_stage", True, steps)
        if len(path) >= inst.max_depth:
            continue
        for dest in sorted({d for (o, d) in inst.arcs if o == node}):
            q.append(path + (dest,))
    return RunResult("two_stage", False, [], note="execution failed")


def run_standard_rh_robust(inst: TinyInstance, scenario: dict[tuple[str, str], ArcMode]) -> RunResult:
    """Standard RH: open-loop replan from the current information state each step."""
    state = initial_state(inst)
    steps: list[StepRecord] = []
    for _ in range(inst.max_depth * 3):
        if terminal_ok(inst, state):
            return RunResult("rh_open_loop", True, steps)
        plan = _open_loop_plan_return_to(inst, state)
        if not plan:
            return RunResult("rh_open_loop", False, steps, note="no OL replan")
        kind, arg = plan[0]
        if kind == "c":
            steps.append(StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"charge:{arg}"))
            nxt = apply_charge(inst, state, int(arg))
            if nxt is None:
                return RunResult("rh_open_loop", False, steps, note="charge failed")
            state = nxt
        else:
            dest = str(arg)
            mode = scenario.get((state.node, dest))
            if mode is None:
                adm = _admissible(inst, state, dest)
                if not adm:
                    return RunResult("rh_open_loop", False, steps, note="no mode")
                mode = adm[0]
            steps.append(
                StepRecord(state.time, state.node, state.soc, state.gamma_rem, f"travel:{dest}", mode.name)
            )
            nxt = apply_travel(inst, state, dest, mode)
            if nxt is None:
                return RunResult("rh_open_loop", False, steps, note="travel failed")
            state = nxt
    return RunResult("rh_open_loop", terminal_ok(inst, state), steps, note="horizon exhausted")


def compare_controllers(inst: TinyInstance) -> dict:
    """Matched comparison across oracle modes and gamma-feasible scenarios."""
    oracle = {
        "open_loop": evaluate_mode(inst, "open_loop").value,
        "two_stage": evaluate_mode(inst, "two_stage").value,
        "feedback": evaluate_mode(inst, "feedback").value,
        "clairvoyant": evaluate_mode(inst, "clairvoyant").value,
        "certificate": terminal_viability_certificate(inst).value,
    }
    arc_keys = sorted(inst.arcs.keys())
    scenarios = []
    for combo in product(*[inst.arcs[a] for a in arc_keys]):
        if sum(m.z for m in combo) > inst.gamma:
            continue
        scenarios.append({a: m for a, m in zip(arc_keys, combo, strict=True)})

    runs = []
    for scen in scenarios:
        runs.append(
            {
                "scenario": {f"{a[0]}->{a[1]}": m.name for a, m in scen.items()},
                "open_loop": run_open_loop(inst, scen).success,
                "two_stage": run_two_stage_then_execute(inst, scen).success,
                "feedback_mpc": run_feedback_mpc(inst, scen).success,
                "rh_open_loop": run_standard_rh_robust(inst, scen).success,
            }
        )
    return {"instance": inst.name, "oracle": oracle, "runs": runs}
