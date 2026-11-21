"""Family-fit forecast loaders for mpc_paper_family_forecast_v1.

Same MPC class everywhere; arrival/finite-demand priors are fit only on the
matching dataset family's predeclared train freeze.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.evrp_tw_d import extract_root, list_solomon_files
from safe_time_evrp.data.paths import evrp_tw_d_dir
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    FiniteDemandModel,
    FiniteDemandTrainEpisode,
    fit_finite_demand_model,
    fit_finite_demand_model_from_episodes,
)
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, fit_empirical_arrivals
from safe_time_evrp.mpc_central.mpc_paper_eval import _evrp_dynamic_case

ROOT = Path(__file__).resolve().parents[3]
EVRP_FAMILY_SPLITS = ROOT / "docs" / "experiments" / "MPC_EVRP_FAMILY_SPLITS.json"


@dataclass(frozen=True)
class FamilyForecastPack:
    family: str
    arrival: ArrivalForecast
    finite: FiniteDemandModel
    train_meta: dict


def _load_evrp_splits() -> dict:
    return json.loads(EVRP_FAMILY_SPLITS.read_text(encoding="utf-8"))


def assert_evrp_train_test_disjoint(splits: dict | None = None) -> None:
    splits = splits or _load_evrp_splits()
    for scale in ("Cus_5", "Cus_15"):
        train = set(splits["train_freeze"][scale])
        test = set(splits["test_freeze"][scale])
        overlap = sorted(train & test)
        if overlap:
            raise ValueError(f"EVRP train/test overlap on {scale}: {overlap}")


def _evrp_train_cases(splits: dict) -> list[tuple[str, int, BaselineCase]]:
    root = extract_root(evrp_tw_d_dir())
    out: list[tuple[str, int, BaselineCase]] = []
    for scale in ("Cus_5", "Cus_15"):
        idxs = list(splits["train_freeze"][scale])
        files = list_solomon_files(root, scale=scale)
        for idx in idxs:
            if idx >= len(files):
                continue
            path = files[idx]
            case = _evrp_dynamic_case(path, scale=scale, pol=11)
            out.append((scale, idx, case))
    return out


def load_family_forecasts(family: str) -> FamilyForecastPack:
    """Fit arrival + finite-demand models for ``schneider`` or ``evrp_tw_d``."""
    key = family.strip().lower()
    if key in {"schneider", "schneider_evrptw"}:
        splits = stratified_split_small()
        train_stems = list(splits["train"])
        arrival = fit_empirical_arrivals([load_instance(s) for s in train_stems])
        finite = fit_finite_demand_model(dynamicity="medium", n_realizations=3)
        return FamilyForecastPack(
            family="schneider",
            arrival=arrival,
            finite=finite,
            train_meta={"stems": train_stems, "n_stems": len(train_stems)},
        )
    if key in {"evrp_tw_d", "evrp"}:
        splits = _load_evrp_splits()
        assert_evrp_train_test_disjoint(splits)
        cases = _evrp_train_cases(splits)
        if not cases:
            raise RuntimeError("EVRP train freeze produced zero cases")
        instances = [c.instance for _, _, c in cases]
        arrival = fit_empirical_arrivals(instances)
        episodes: list[FiniteDemandTrainEpisode] = []
        for _scale, _idx, case in cases:
            cust = list(case.instance.customer_ids())
            n_known = max(1, int(0.3 * len(cust)))
            known = set(cust[:n_known])
            dyn = set(cust[n_known:])
            episodes.append(
                FiniteDemandTrainEpisode(
                    n_customers=len(cust),
                    horizon=float(case.horizon),
                    releases=list(case.releases),
                    dynamic_arrivals=dyn,
                    known_at_start=known,
                    instance=case.instance,
                )
            )
        finite = fit_finite_demand_model_from_episodes(
            episodes,
            train_atoms=arrival.train_atoms,
            model_id=(
                f"finite_demand_v1;family=evrp_tw_d;train_cells={len(episodes)};"
                f"protocol=mpc_paper_family_forecast_v1"
            ),
            protocol_version="evrp_tw_d_family_v1",
        )
        train_index = {
            scale: list(splits["train_freeze"][scale]) for scale in ("Cus_5", "Cus_15")
        }
        return FamilyForecastPack(
            family="evrp_tw_d",
            arrival=arrival,
            finite=finite,
            train_meta={
                "train_freeze_indices": train_index,
                "n_train_cells": len(episodes),
                "splits_path": str(EVRP_FAMILY_SPLITS.as_posix()),
            },
        )
    raise ValueError(f"unknown forecast family: {family!r}")
