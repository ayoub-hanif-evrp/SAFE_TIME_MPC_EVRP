"""Safe dual MPC research package (energy learning under delivery commitments).

Gate 3–4 controllers remain comparison baselines. This package studies whether
information-aware routing under irrevocable EVRP commitments yields an EV-specific
dual-control effect beyond Åkerblom-style energy navigation learning.
"""

from safe_time_evrp.dual_mpc.belief import BoundedErrorSet, DiscreteBelief
from safe_time_evrp.dual_mpc.energy_param import ParametricEnergy, SharedThetaWorld
from safe_time_evrp.dual_mpc.exact_oracle import DualControlExactReport, run_exact_dual_example

__all__ = [
    "BoundedErrorSet",
    "DiscreteBelief",
    "DualControlExactReport",
    "ParametricEnergy",
    "SharedThetaWorld",
    "run_exact_dual_example",
]
