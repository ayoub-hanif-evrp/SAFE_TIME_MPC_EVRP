"""Train / development / holdout splits for Phase 3D (information-safe forecasts).

Holdout is reserved and must not be used for forecast fitting or controller tuning.
"""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase, build_baseline_suite
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, build_anonymous_scenarios, fit_empirical_arrivals
from safe_time_evrp.mpc3c.seeds import stable_seed

# Explicit frozen split over the small baseline suite.
TRAIN_CASE_IDS: tuple[str, ...] = ("B_tight_battery", "B_competing")
DEV_CASE_IDS: tuple[str, ...] = ("B_phase_b", "B_easy_dynamic")
HOLDOUT_CASE_IDS: tuple[str, ...] = ("B_adversarial_overaccept",)


def _by_id() -> dict[str, BaselineCase]:
    return {c.case_id: c for c in build_baseline_suite()}


def train_cases() -> list[BaselineCase]:
    table = _by_id()
    return [table[i] for i in TRAIN_CASE_IDS]


def development_cases() -> list[BaselineCase]:
    table = _by_id()
    return [table[i] for i in DEV_CASE_IDS]


def holdout_cases() -> list[BaselineCase]:
    """Reserved — do not evaluate until a credible development mechanism win exists."""
    table = _by_id()
    return [table[i] for i in HOLDOUT_CASE_IDS]


def fit_train_forecast(*, n_scenarios: int = 2, customers_per_scenario: int = 2, seed: int = 0) -> ArrivalForecast:
    """Fit anonymous arrival atoms on **train cases only**, then materialize scenarios."""
    instances = [c.instance for c in train_cases()]
    model = fit_empirical_arrivals(instances)
    return build_anonymous_scenarios(
        model,
        n_scenarios=n_scenarios,
        customers_per_scenario=customers_per_scenario,
        seed=stable_seed("phase3d_train_forecast", str(seed)),
    )


def split_manifest() -> dict:
    return {
        "train": list(TRAIN_CASE_IDS),
        "development": list(DEV_CASE_IDS),
        "holdout": list(HOLDOUT_CASE_IDS),
        "holdout_status": "untouched",
        "forecast_rule": "fit_empirical_arrivals on train instances only; anonymous scenarios only",
    }
