"""Robust certificates, certified backups, and deadline-aware MPC."""

from safe_time_evrp.robust.certificate import Verdict, certify
from safe_time_evrp.robust.uncertainty import RectangularUncertainty

__all__ = ["RectangularUncertainty", "Verdict", "certify"]
