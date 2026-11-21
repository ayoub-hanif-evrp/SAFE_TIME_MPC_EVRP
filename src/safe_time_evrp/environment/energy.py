"""Energy / charging models — **nonlinear charging only**.

Travel energy remains the instance arc energy (benchmark consumption × distance).
Charging uses a concave piecewise-linear rate curve (Montoya-style), calibrated so
a full 0→Q charge takes the same wall time as the instance's legacy ``g * Q``
scale factor (``inverse_recharge_rate * battery_capacity``). There is no linear
``g * (target - soc)`` charging path.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Arc, Instance

EPS = 1e-9

# Concave piecewise-linear charge curve (SoC fraction → relative power).
# Power decreases as SoC rises; final segment approaches 0 at full pack.
_DEFAULT_BREAKPOINTS: tuple[float, ...] = (0.0, 0.80, 0.90, 1.00)
_DEFAULT_RELATIVE_POWER: tuple[float, ...] = (1.00, 0.70, 0.40, 0.05)


class EnergyModelError(ValueError):
    pass


def _piecewise_charge_time(
    soc: float,
    target: float,
    battery_capacity: float,
    *,
    breakpoints: tuple[float, ...],
    relative_power: tuple[float, ...],
    full_charge_time: float,
) -> float:
    """Time to charge from ``soc`` to ``target`` under a concave PWL curve.

    ``full_charge_time`` is the wall time for 0→Q used to scale relative powers
    into absolute energy/time units.
    """
    if target < soc - EPS:
        raise EnergyModelError("charge target is below the current state of charge")
    if battery_capacity <= EPS:
        raise EnergyModelError("battery capacity must be positive")
    if full_charge_time < 0:
        raise EnergyModelError("full charge time cannot be negative")
    if abs(target - soc) <= EPS:
        return 0.0

    q = float(battery_capacity)
    # Relative energy under the unscaled curve for 0→Q (for calibration).
    rel_full = _integrate_relative(0.0, q, q, breakpoints, relative_power)
    if rel_full <= EPS:
        raise EnergyModelError("degenerate charging curve")
    # Absolute rate scale: energy/time such that ∫_0^Q dt = full_charge_time.
    # relative integral measures ∫ dE / p_rel; time = (rel_integral / rel_full) * full_charge_time.
    rel = _integrate_relative(soc, target, q, breakpoints, relative_power)
    return full_charge_time * (rel / rel_full)


def _integrate_relative(
    soc: float,
    target: float,
    q: float,
    breakpoints: tuple[float, ...],
    relative_power: tuple[float, ...],
) -> float:
    """∫_{soc}^{target} dE / p_rel(E) with p_rel piecewise-linear in SoC fraction."""
    if len(breakpoints) != len(relative_power) or len(breakpoints) < 2:
        raise EnergyModelError("breakpoints and relative_power length mismatch")
    lo = max(0.0, min(float(soc), float(target)))
    hi = min(q, max(float(soc), float(target)))
    if hi <= lo + EPS:
        return 0.0
    total = 0.0
    for i in range(len(breakpoints) - 1):
        a_frac, b_frac = breakpoints[i], breakpoints[i + 1]
        a_e, b_e = a_frac * q, b_frac * q
        seg_lo = max(lo, a_e)
        seg_hi = min(hi, b_e)
        if seg_hi <= seg_lo + EPS:
            continue
        p0, p1 = relative_power[i], relative_power[i + 1]
        # Bind loop vars as defaults so the nested function does not close over the loop.
        def p_at(
            e: float,
            *,
            _a: float = a_e,
            _b: float = b_e,
            _p0: float = p0,
            _p1: float = p1,
        ) -> float:
            if abs(_b - _a) <= EPS:
                return max(EPS, 0.5 * (_p0 + _p1))
            t = (e - _a) / (_b - _a)
            return max(EPS, _p0 + (_p1 - _p0) * t)

        p_lo = p_at(seg_lo)
        p_hi = p_at(seg_hi)
        if abs(p_hi - p_lo) <= 1e-12:
            total += (seg_hi - seg_lo) / p_lo
        else:
            slope = (p1 - p0) / (b_e - a_e) if abs(b_e - a_e) > EPS else 0.0
            if abs(slope) <= EPS:
                total += (seg_hi - seg_lo) / p_lo
            else:
                total += (1.0 / slope) * (math_log(p_hi) - math_log(p_lo))
    return total


def math_log(x: float) -> float:
    import math

    return math.log(max(x, EPS))


@dataclass(frozen=True)
class NonlinearPiecewiseChargeEnergy:
    """Benchmark travel energy + concave piecewise-linear charging (only model)."""

    name: str = "nonlinear_piecewise_charge"
    breakpoints: tuple[float, ...] = _DEFAULT_BREAKPOINTS
    relative_power: tuple[float, ...] = _DEFAULT_RELATIVE_POWER

    def travel_energy(
        self,
        instance: Instance,
        arc: Arc,
        *,
        soc: float,
        load: float,
    ) -> float:
        del soc, load
        if arc.energy < -EPS:
            raise EnergyModelError("arc energy is negative")
        return arc.energy

    def charge_duration(
        self,
        soc: float,
        target: float,
        inverse_rate: float,
        *,
        battery_capacity: float | None = None,
    ) -> float:
        """Nonlinear charge time.

        ``inverse_rate`` is kept as the instance scale factor: full 0→Q time equals
        ``inverse_rate * Q`` (same numerical scale as legacy Schneider ``g``), but
        intermediate SoC segments are slower near full pack (concave curve).
        """
        if inverse_rate < 0:
            raise EnergyModelError("inverse recharge rate is negative")
        q = float(battery_capacity) if battery_capacity is not None else max(float(target), float(soc), EPS)
        full_time = inverse_rate * q
        return _piecewise_charge_time(
            float(soc),
            float(target),
            q,
            breakpoints=self.breakpoints,
            relative_power=self.relative_power,
            full_charge_time=full_time,
        )

    def description(self) -> str:
        return (
            "Travel energy = benchmark arc energy. Charging = concave piecewise-linear "
            f"curve breakpoints={self.breakpoints} relative_power={self.relative_power}; "
            "no linear g*(target-soc) charging."
        )


# Canonical name used across the codebase.
EnergyModel = NonlinearPiecewiseChargeEnergy


@dataclass(frozen=True)
class ScaledEnergy:
    """Test double: scales travel energy only; charging stays nonlinear."""

    factor: float
    name: str = "scaled_travel_energy"
    _inner: NonlinearPiecewiseChargeEnergy = NonlinearPiecewiseChargeEnergy()

    def __post_init__(self) -> None:
        if self.factor < 0:
            raise EnergyModelError("energy scale cannot be negative")

    def travel_energy(
        self,
        instance: Instance,
        arc: Arc,
        *,
        soc: float,
        load: float,
    ) -> float:
        return self.factor * self._inner.travel_energy(instance, arc, soc=soc, load=load)

    def charge_duration(
        self,
        soc: float,
        target: float,
        inverse_rate: float,
        *,
        battery_capacity: float | None = None,
    ) -> float:
        return self._inner.charge_duration(
            soc, target, inverse_rate, battery_capacity=battery_capacity
        )

    def description(self) -> str:
        return f"Travel energy × {self.factor}; nonlinear charging unchanged."


@dataclass(frozen=True)
class LinearChargeEnergy:
    """Ablation-only planner: charge duration = g * (target - soc).

    Plant / replay remain nonlinear. Using this for MPC planning creates the
    Montoya-style model mismatch the paper claims nonlinear charging fixes.
    """

    name: str = "linear_charge_ablation"

    def travel_energy(
        self,
        instance: Instance,
        arc: Arc,
        *,
        soc: float,
        load: float,
    ) -> float:
        del soc, load
        if arc.energy < -EPS:
            raise EnergyModelError("arc energy is negative")
        return arc.energy

    def charge_duration(
        self,
        soc: float,
        target: float,
        inverse_rate: float,
        *,
        battery_capacity: float | None = None,
    ) -> float:
        del battery_capacity
        if inverse_rate < 0:
            raise EnergyModelError("inverse recharge rate is negative")
        if target < soc - EPS:
            raise EnergyModelError("charge target is below the current state of charge")
        return inverse_rate * max(0.0, float(target) - float(soc))

    def description(self) -> str:
        return "Ablation: linear g*(target-soc) charge duration (planning mismatch vs nonlinear plant)."


# Production default remains nonlinear. NominalLinearEnergy is a legacy alias.
NominalLinearEnergy = NonlinearPiecewiseChargeEnergy  # noqa: N816 — legacy name
ScaledNominalEnergy = ScaledEnergy
