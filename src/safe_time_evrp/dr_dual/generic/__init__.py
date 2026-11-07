"""Generic finite-state dual EVRP–MPC reference (not A/C/S-hardcoded)."""

from safe_time_evrp.dr_dual.generic.exact_dp import solve_generic_exact
from safe_time_evrp.dr_dual.generic.general_bound import evaluate_generic_resource_bound
from safe_time_evrp.dr_dual.generic.model import make_tiny_generic_instance

__all__ = [
    "evaluate_generic_resource_bound",
    "make_tiny_generic_instance",
    "solve_generic_exact",
]
