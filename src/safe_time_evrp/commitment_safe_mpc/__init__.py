"""Commitment-safe / computation-aware MPC for dynamic EVRP.

Phase B establishes ``FleetSimulator`` + ``validation.replay`` as the authoritative
physical plant. Dual-control toys remain optional artifacts under ``dr_dual``.
"""

from safe_time_evrp.commitment_safe_mpc.plant import AUTHORITATIVE_PLANT, AuthoritativePlant

__all__ = ["AUTHORITATIVE_PLANT", "AuthoritativePlant"]
