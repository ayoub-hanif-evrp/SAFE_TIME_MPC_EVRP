"""Commitment-safe / computation-aware MPC for dynamic EVRP.

Phase B establishes ``FleetSimulator`` + ``validation.replay`` as the authoritative
physical plant. Dual-control toys remain optional artifacts under ``dr_dual``.

Import leaf modules directly (e.g. ``public_snapshot``, ``alns_mpc``, ``plant``).
This package ``__init__`` deliberately imports nothing so controllers can load
``public_snapshot`` without pulling ``plant`` → ``episode`` into a cycle.
"""

__all__: list[str] = []
