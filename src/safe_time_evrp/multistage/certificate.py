"""Attempted terminal-viability certificate (Gate C).

This is deliberately the standard robust Bellman / labeling recursion on the discrete
model. Soundness is immediate from the feedback oracle; novelty is not claimed.
"""

from __future__ import annotations

from safe_time_evrp.multistage.model import TinyInstance
from safe_time_evrp.multistage.oracle import Status, feedback_feasible, initial_state


def terminal_viability_certificate(inst: TinyInstance) -> Status:
    """Return PROVEN_FEASIBLE iff a causal winning policy exists from the initial state.

    Equivalent to ``feedback_feasible``. Documented in PROOF_ATTEMPTS.md as collapsing
    to generic robust DP / labeling rather than an EVRP-specific closed-form bound.
    """
    return feedback_feasible(inst)


def certify_state(inst: TinyInstance) -> dict:
    status = terminal_viability_certificate(inst)
    root = initial_state(inst)
    return {
        "status": status.value,
        "method": "robust_bellman_labeling",
        "state": {
            "time": root.time,
            "node": root.node,
            "soc": root.soc,
            "remaining": sorted(root.remaining),
            "gamma_rem": root.gamma_rem,
        },
        "novelty": False,
        "note": "Identical to exact multistage feedback feasibility DP.",
    }
