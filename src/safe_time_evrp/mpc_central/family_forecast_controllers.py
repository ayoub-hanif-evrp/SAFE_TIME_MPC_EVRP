"""Shared proposed-stack factory for family-forecast campaigns."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.mpc_central.family_forecasts import FamilyForecastPack
from safe_time_evrp.mpc_central.mpc_paper_eval import ALNS_ITER


def make_proposed_mpc(
    case: BaselineCase,
    *,
    cfg: dict,
    pack: FamilyForecastPack | None,
    pol: int,
    budget: float,
    alns_iterations: int = ALNS_ITER,
    n_scenarios: int | None = None,
    rollout_max_events: int = 100,
    use_forecast: bool | None = None,
    force_empty: bool = False,
) -> CommitmentSafeStochasticMpc:
    """Build proposed CSS-MPC; ``force_empty`` overrides to empty-future ablation."""
    want_forecast = False if force_empty else (
        bool(cfg.get("use_forecast", True)) if use_forecast is None else bool(use_forecast)
    )
    n_sc = int(n_scenarios if n_scenarios is not None else cfg.get("n_scenarios", 2))
    if not want_forecast:
        n_sc = 1
    kwargs = dict(
        use_forecast=want_forecast,
        n_scenarios=n_sc,
        require_terminal_commitment=True,
        spi_mode=True,
        spi_advantage_margin=0.0,
        hard_terminal_accepts=bool(cfg.get("hard_terminal_accepts", True)),
        accept_slack_gate=bool(cfg.get("accept_slack_gate", True)),
        gamma_time=float(cfg.get("gamma_time", 0.0)),
        gamma_energy=float(cfg.get("gamma_energy", 0.0)),
        accept_score_penalty=float(cfg.get("accept_score_penalty", 50.0)),
        charge_first_soc_frac=(
            None
            if cfg.get("charge_first_soc_frac", 0.2) is None
            else float(cfg.get("charge_first_soc_frac", 0.2))
        ),
        max_new_accepts=(
            None if cfg.get("max_new_accepts") is None else int(cfg["max_new_accepts"])
        ),
        alns_iterations=int(alns_iterations),
        time_limit_seconds=float(budget),
        seed=int(pol),
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=int(rollout_max_events),
        selection_mode=str(cfg.get("selection_mode", "msa_consensus")),
        scenario_sample_mode=str(cfg.get("scenario_sample_mode", "stratified")),
        adaptive_compute=bool(cfg.get("adaptive_compute", True)),
        n_scenarios_max=int(cfg.get("n_scenarios_max", max(n_sc, 4))),
        alns_iterations_max=int(cfg.get("alns_iterations_max", max(alns_iterations, 20))),
    )
    if want_forecast:
        if pack is None:
            raise ValueError("forecast-on proposed stack requires a FamilyForecastPack")
        kwargs.update(
            forecast=pack.arrival,
            finite_demand_model=pack.finite,
            use_finite_demand=True,
        )
    return CommitmentSafeStochasticMpc(case.instance, case.horizon, **kwargs)
