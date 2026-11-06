"""Process-isolated solver supervisor.

The deadline includes process startup, transfer, and the caller's validation.
A worker that misses the deadline is terminated. Cooperative clock checks are
not used on this path.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


class SupervisorError(RuntimeError):
    pass


def _serve(conn) -> None:
    from safe_time_evrp.robust.anytime import improve

    while True:
        try:
            message = conn.recv()
        except EOFError:
            return
        if message is None:
            return
        op = message.get("op")
        state_id = message.get("state_id", "")
        try:
            if op == "sleep":
                time.sleep(float(message["seconds"]))
                conn.send({"state_id": state_id, "final": True, "ok": True, "tag": "slept"})
            elif op == "boom":
                raise RuntimeError("injected solver exception")
            elif op == "crash":
                os._exit(3)
            elif op == "improve":
                produced = False
                for item in improve(
                    message["instance"],
                    message["observation"],
                    message["incumbent"],
                    message["uncertainty"],
                    steps=int(message["steps"]),
                    horizon=float(message["horizon"]),
                    allowed_customers=message.get("allowed_customers"),
                ):
                    produced = True
                    conn.send({"state_id": state_id, "final": False, "ok": True, "candidate": item})
                if not produced:
                    conn.send(
                        {
                            "state_id": state_id,
                            "final": True,
                            "ok": True,
                            "candidate": {
                                "routes": message["incumbent"],
                                "newly_accepted": [],
                                "rejected": [],
                                "examined": 0,
                                "certificate_ok": False,
                                "final": True,
                            },
                        }
                    )
                else:
                    conn.send({"state_id": state_id, "final": True, "ok": True, "candidate": None})
            else:
                conn.send({"state_id": state_id, "final": True, "ok": False, "error": f"unknown op {op}"})
        except Exception as exc:
            conn.send({"state_id": state_id, "final": True, "ok": False, "error": repr(exc)})


@dataclass
class SupervisorResult:
    status: str
    elapsed: float
    accepted_message: dict | None = None
    error: str = ""
    messages: int = 0
    details: dict = field(default_factory=dict)


class SolverSupervisor:
    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._process: mp.Process | None = None
        self._conn = None

    def close(self) -> None:
        self._kill()

    def _kill(self) -> None:
        process = self._process
        conn = self._conn
        self._process = None
        self._conn = None
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(1.0)
        if process.is_alive():
            process.kill()
            process.join(1.0)
        process.close()

    def _ensure(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        parent, child = self._ctx.Pipe(duplex=True)
        process = self._ctx.Process(target=_serve, args=(child,), daemon=True)
        process.start()
        child.close()
        self._process = process
        self._conn = parent

    def run(
        self,
        payload: dict,
        deadline: float,
        state_id: str,
        validate,
    ) -> SupervisorResult:
        if deadline <= 0:
            raise SupervisorError("deadline must be positive")
        started = perf_counter()
        limit = started + deadline
        try:
            self._ensure()
        except Exception as exc:
            self._kill()
            return SupervisorResult("crash", perf_counter() - started, error=repr(exc))
        if perf_counter() > limit or self._conn is None:
            self._kill()
            return SupervisorResult("timeout", perf_counter() - started, details={"phase": "startup"})
        message = dict(payload)
        message["state_id"] = state_id
        try:
            self._conn.send(message)
        except (EOFError, OSError, BrokenPipeError) as exc:
            self._kill()
            return SupervisorResult("crash", perf_counter() - started, error=repr(exc))
        accepted: dict | None = None
        count = 0
        finished = False
        error = ""
        while perf_counter() < limit:
            timeout = max(0.0, min(0.02, limit - perf_counter()))
            try:
                ready = self._conn.poll(timeout)
            except (EOFError, OSError, BrokenPipeError) as exc:
                self._kill()
                return SupervisorResult("crash", perf_counter() - started, error=repr(exc), messages=count)
            if not ready:
                if self._process is not None and not self._process.is_alive():
                    self._kill()
                    return SupervisorResult(
                        "crash",
                        perf_counter() - started,
                        error="worker exited",
                        messages=count,
                    )
                continue
            try:
                incoming: dict[str, Any] = self._conn.recv()
            except (EOFError, OSError, BrokenPipeError) as exc:
                self._kill()
                return SupervisorResult("crash", perf_counter() - started, error=repr(exc), messages=count)
            count += 1
            if perf_counter() > limit:
                break
            if incoming.get("state_id") != state_id:
                continue
            if incoming.get("ok") is False:
                error = str(incoming.get("error", "solver error"))
                finished = True
                break
            candidate = incoming.get("candidate")
            if candidate is not None:
                try:
                    verdict = validate(candidate)
                except Exception as exc:
                    self._kill()
                    return SupervisorResult("crash", perf_counter() - started, error=repr(exc), messages=count)
                if perf_counter() > limit:
                    accepted = None
                    break
                if verdict is not None:
                    accepted = {"candidate": candidate, "validation": verdict}
            if incoming.get("final"):
                finished = True
                break
        elapsed = perf_counter() - started
        if not finished:
            self._kill()
            if accepted is None:
                return SupervisorResult("timeout", elapsed, messages=count, error=error)
            return SupervisorResult("partial", elapsed, accepted, messages=count)
        if error:
            return SupervisorResult("error", elapsed, error=error, messages=count)
        return SupervisorResult("ok", elapsed, accepted, messages=count)
