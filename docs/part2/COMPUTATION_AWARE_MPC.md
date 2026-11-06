# Computation-aware MPC

## Deadline

Every certified controller in a comparison uses one deadline \(T_{\mathrm{deadline}}\). The experimental values are 0.1 s, 0.5 s, 1 s, and 5 s. Checking a clock after a function returns is not an implementation of that deadline. The supervisor is a separate process.

`SolverSupervisor` in `robust/supervisor.py`:

- keeps the backup in the parent process,
- sends one snapshot and one action identity to the worker,
- counts process start, transfer, and the parent's validation inside the deadline,
- terminates the worker when the deadline expires, and kills it if `terminate` does not return,
- treats a worker exception as `error` and a dead pipe or `os._exit` as `crash`,
- discards a message whose action identity does not match the snapshot,
- discards a validation that finishes after the deadline.

A partial anytime message that was validated before the deadline may be committed. A message that arrives after the kill is not read. The parent closes the pipe and the process.

The timeout test sleeps for 30 s with a 0.4 s deadline, requires the status `timeout`, and requires the process handle to be cleared. A following short job must still be able to run, which checks that the supervisor can start a new worker. An injected exception and an injected `os._exit` are separate tests.

## Plant time

Wall time of a decision is plant time, with one rule. Let the decision begin at plant time \(t\) and last \(\delta\) seconds on the wall clock.

- If the next physical event is at \(t' \le t+\delta\), the candidate is not committed. The event is left on the heap and is processed next. The plant was not frozen through that event.
- If no physical event falls in \((t, t+\delta]\), the plant clock becomes \(t+\delta\) and the candidate is certified again at the new clock before `commit`.

Idle vehicles use the new clock as their anchor. A vehicle that is traveling keeps the anchor already predicted for the end of that arc. The action identity ignores the idle clock and includes status, node, locked destination, battery, load, and the accepted set. A change in that identity makes `commit` return false and drop the staged plan. Case D tests that refusal.

This is not a proof that every deadline is met. A cold process start on Windows can consume a 0.1 s budget before the worker runs. The 0.1 s budget is therefore an experimental setting that can force the backup, not a claim that the machine finishes a useful solve in 0.1 s.

## Anytime candidates

The worker runs a deterministic insertion loop (`robust/anytime.py`). It starts from the current backup, strips visits that are already behind the anchor, and tries a bounded number of certified insertions. Each certified fleet plan is sent to the parent. The parent keeps the last one whose validation finished before the deadline. There is no ALNS library.

Anytime insertion is prior art. The only rule added here is that the parent, not the worker, commits the backup.

## Proposition 4 (idle delay)

Assume A1–A7 and Proposition 1. Suppose every vehicle is idle, a sequence is certified from time \(t+\Delta\), and execution of that same sequence starts at time \(t+\delta\) with \(0 \le \delta \le \Delta\), with the same batteries and the same commitments. Then the sequence remains robustly feasible.

**Proof.** Starting earlier than the certified clock, with the same battery, only increases the slack in Lemma 1. The implementation does not rely on this inequality alone. It re-runs the certificate at the clock at which the plan will start, and commits only if that call passes. \(\square\)

If a vehicle is not idle, Proposition 4 does not apply. The plan must be a suffix from the predicted end of the locked action, and it is discarded when that action's identity changes.

## What was not shown

No theorem says the insertion loop terminates with a better plan inside the deadline. On a timeout the backup is kept if it is still certified from the current anchor. If it is not, the controller reports `no_feasible_continuation` and does not start the infeasible arc. Case G.
