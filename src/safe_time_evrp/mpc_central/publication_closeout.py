"""Final publication integrity closeout — no algorithm pivots."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Visit
from safe_time_evrp.mpc_central.accelerated_pilot import build_accelerated_dev_matrix
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.certificate_theory import theorem_document
from safe_time_evrp.mpc_central.phase3d_splits import (
    HOLDOUT_CASE_IDS,
    fit_train_forecast,
    holdout_cases,
    split_manifest,
)
from safe_time_evrp.validation.replay import validate_log

FOCUS_CASES = ("A_dense_arrivals", "A_low_soc_charge", "B_easy_dynamic")
SEED_MANIFEST = (3, 7, 11)
ALNS_ITER = 10
ALNS_TIME = 0.35


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def _case_map():
    return {c.case_id: c for c in build_accelerated_dev_matrix()}


def audit_certificate_accounting(*, seed: int = 7) -> dict:
    """Reproduce low-SOC regression; assert CERTIFIED ⇒ independent coverage."""
    case = _case_map()["A_low_soc_charge"]
    forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
    ctrl = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        forecast=forecast,
        n_scenarios=2,
        alns_iterations=8,
        time_limit_seconds=0.45,
        seed=seed,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=150,
    )
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    epochs = []
    events = 0
    replan = None
    certified_verify_failures = 0
    unknown_with_accepted = 0
    publish_accepted_mismatches = 0

    while events < 600:
        nxt = sim.next_event_time()
        if nxt is None or nxt > case.t_max:
            break
        ev = sim.pop_event()
        events += 1
        if ev is None:
            break
        if ev.kind not in {"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan"}:
            continue
        obs = sim.observation()
        d = ctrl.decide(obs, ev.kind)
        public = make_public_snapshot(case.instance, obs, case.horizon).instance
        pending = set(obs.accepted) - set(obs.completed) - set(obs.in_service)
        post_accepted = set(d.accepted)
        status = ctrl.last_validation_status
        indep = validate_continuation(public, obs, d.routes, require_new=frozenset(d.newly_accepted))
        if status == "CERTIFIED_FEASIBLE" and not indep.ok:
            certified_verify_failures += 1
        if status == "UNKNOWN" and (pending or (post_accepted - set(obs.completed) - set(obs.in_service))):
            unknown_with_accepted += 1
        cert = ctrl.store.current
        if status == "CERTIFIED_FEASIBLE" and cert is not None:
            # Post-decision accepted must be recorded on the certificate.
            if not set(d.newly_accepted) <= set(cert.accepted):
                publish_accepted_mismatches += 1
            if not set(d.accepted) <= set(cert.accepted) | set(obs.completed) | set(obs.in_service):
                publish_accepted_mismatches += 1
        epochs.append(
            {
                "time": obs.time,
                "trigger": ev.kind,
                "status": status,
                "independent_ok": indep.ok,
                "pending_before": sorted(pending),
                "newly_accepted": list(d.newly_accepted),
                "accepted_post": list(d.accepted),
                "obligation_gap": list(ctrl.last_obligation_gap),
                "cert_version": None if cert is None else cert.version,
                "cert_accepted": None if cert is None else sorted(cert.accepted),
                "fallback": d.fallback_used,
            }
        )
        # Illegal admission probe once
        if obs.completed and events == 8:
            cid = next(iter(obs.completed))
            bad_routes = {v.id: [Visit(cid, "service")] for v in obs.vehicles}
            bad = validate_continuation(public, obs, bad_routes, require_new=frozenset({cid}))
            epochs.append(
                {
                    "time": obs.time,
                    "trigger": "forced_illegal_probe",
                    "illegal_blocked": not bad.ok,
                    "reasons": list(bad.reasons)[:4],
                }
            )
        try:
            sim.apply_decision(d)
        except Exception as exc:  # noqa: BLE001
            epochs.append({"time": obs.time, "apply_error": str(exc)})
            break
        if replan is not None:
            sim.cancel(replan)
        replan = sim.schedule_replan(sim.time + case.max_replan_interval)

    report = validate_log(case.instance, sim.log)
    # Find any UNKNOWN-with-accepted around t=73 for documentation
    gap_epochs = [e for e in epochs if e.get("status") == "UNKNOWN" and e.get("obligation_gap")]
    return {
        "case_id": case.case_id,
        "seed": seed,
        "n_epochs": len(epochs),
        "certified_verify_failures": certified_verify_failures,
        "unknown_with_accepted": unknown_with_accepted,
        "publish_accepted_mismatches": publish_accepted_mismatches,
        "gap_epochs_sample": gap_epochs[:5],
        "replay_ok": report.ok,
        "replay_code": report.code,
        "pass_accounting": (certified_verify_failures == 0 and publish_accepted_mismatches == 0 and report.ok),
        "notes": (
            "UNKNOWN-with-accepted may still occur as an honest obligation gap; "
            "it must never be labeled CERTIFIED_FEASIBLE."
        ),
        "epochs_sample": epochs[:8],
    }


def source_level_comparison() -> dict:
    return {
        "b1": {
            "module": "commitment_safe_mpc.full_validation_mpc.FullValidationAlnsMpc",
            "certificate_store": False,
            "forecast_ev_ranking": False,
            "fallback": "empty / prior validated routes locally",
        },
        "m1": {
            "module": "commitment_safe_mpc.m1_mpc.CertificateCarryingAlnsMpc",
            "certificate_store": True,
            "store_class": "commitment_safe_mpc.certificate_store.CertificateStore",
            "advance_or_invalidate": True,
            "forecast_ev_ranking": False,
            "fallback": "revalidated previous certificate / verified routes",
        },
        "stochastic_mpc": {
            "module": "commitment_safe_mpc.predictive_mpc.CommitmentSafePredictiveMpc",
            "certificate_store": False,
            "forecast_ev_ranking": True,
            "counterfactual_actions": True,
            "fallback": "previous _verified routes without CertificateStore",
        },
        "cce_mpc": {
            "module": "mpc_central.cce_mpc.CertificateCarryingEconomicMpc",
            "certificate_store": True,
            "store_class": "commitment_safe_mpc.certificate_store.CertificateStore",
            "advance_or_invalidate": True,
            "forecast_ev_ranking": True,
            "counterfactual_actions": True,
            "fallback": "store + _last_certified_routes (M1-style dual retention)",
            "delta_vs_m1": (
                "Adds economic forecast scoring over counterfactual first actions; "
                "reuses the same CertificateStore advancement/revalidation object as M1."
            ),
            "delta_vs_stochastic_mpc": (
                "Adds persistent CertificateStore publish/advance and post-decision accepted "
                "accounting; selection rule is the same EV argmax family."
            ),
        },
    }


def factorial_ablation(*, seeds: tuple[int, ...] = SEED_MANIFEST) -> dict:
    """2×2: certificate persistence × forecast EV scoring on development cases."""
    cases = _case_map()
    rows = []
    for case_id in FOCUS_CASES:
        case = cases[case_id]
        for seed in seeds:
            forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
            configs = {
                "cert_on_forecast_on": dict(use_persistent_certificate=True, use_forecast=True),
                "cert_on_forecast_off": dict(use_persistent_certificate=True, use_forecast=False),
                "cert_off_forecast_on": dict(use_persistent_certificate=False, use_forecast=True),
                "cert_off_forecast_off": dict(use_persistent_certificate=False, use_forecast=False),
                "m1": "m1",
                "b1": "b1",
                "stochastic_mpc": "stoch",
            }
            cell = {"case_id": case_id, "seed": seed, "controllers": {}}
            for name, cfg in configs.items():
                if cfg == "m1":
                    ctrl = CertificateCarryingAlnsMpc(
                        case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=seed
                    )
                elif cfg == "b1":
                    ctrl = FullValidationAlnsMpc(
                        case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=seed
                    )
                elif cfg == "stoch":
                    ctrl = CommitmentSafePredictiveMpc(
                        case.instance,
                        case.horizon,
                        forecast=forecast,
                        n_scenarios=2,
                        alns_iterations=ALNS_ITER,
                        time_limit_seconds=ALNS_TIME,
                        seed=seed,
                        use_counterfactuals=True,
                        use_forecast=True,
                        max_replan_interval=case.max_replan_interval,
                        rollout_max_events=200,
                    )
                else:
                    ctrl = CertificateCarryingEconomicMpc(
                        case.instance,
                        case.horizon,
                        forecast=forecast,
                        n_scenarios=2,
                        alns_iterations=ALNS_ITER,
                        time_limit_seconds=ALNS_TIME,
                        seed=seed,
                        max_replan_interval=case.max_replan_interval,
                        rollout_max_events=200,
                        **cfg,
                    )
                res = run_episode(
                    case.instance,
                    case.releases,
                    fleet_size=case.fleet_size,
                    horizon=case.horizon,
                    max_replan_interval=case.max_replan_interval,
                    t_max=case.t_max,
                    controller=ctrl,
                )
                rep = validate_log(case.instance, res.log)
                final = res.final_requests
                cell["controllers"][name] = {
                    "completed_count": sum(1 for st in final.values() if st == "completed"),
                    "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
                    "executed_distance": executed_distance_from_log(case.instance, res.log),
                    "optimize_seconds": res.optimize_seconds,
                    "replay_ok": rep.ok,
                    "certificate_publishes": getattr(getattr(ctrl, "profile", None), "certificate_publishes", None)
                    or getattr(getattr(ctrl, "profile", None), "certificate_reuses", None),
                    "last_status": getattr(ctrl, "last_validation_status", None),
                }
            rows.append(cell)

    def _agg(key: str):
        vals = []
        for r in rows:
            a = r["controllers"]["cert_on_forecast_on"]
            b = r["controllers"][key]
            if a["replay_ok"] and b["replay_ok"]:
                vals.append(a["completed_count"] - b["completed_count"])
        return {
            "n": len(vals),
            "mean_completed_delta_vs_full_cce": (sum(vals) / len(vals)) if vals else None,
            "n_better": sum(1 for v in vals if v > 0),
            "n_worse": sum(1 for v in vals if v < 0),
            "n_equal": sum(1 for v in vals if v == 0),
        }

    return {
        "seed_manifest": list(seeds),
        "case_ids": list(FOCUS_CASES),
        "factorial": {
            "vs_cert_on_forecast_off": _agg("cert_on_forecast_off"),
            "vs_cert_off_forecast_on": _agg("cert_off_forecast_on"),
            "vs_cert_off_forecast_off": _agg("cert_off_forecast_off"),
            "vs_m1": _agg("m1"),
            "vs_stochastic_mpc": _agg("stochastic_mpc"),
            "vs_b1": _agg("b1"),
        },
        "interpretation": (
            "If cert_on vs cert_off shows no systematic AU/service benefit and store is shared "
            "with M1, the certificate contribution is incremental. Forecast-on vs off isolates "
            "economic scoring."
        ),
        "rows": rows,
    }


def frozen_development_eval() -> dict:
    from safe_time_evrp.mpc_central.final_mpc_package import matched_development_eval

    return matched_development_eval(
        case_ids=FOCUS_CASES, seeds=SEED_MANIFEST, alns_iterations=ALNS_ITER, alns_time=ALNS_TIME
    )


def frozen_holdout_eval() -> dict:
    """Evaluate reserved holdout exactly once under frozen settings."""
    cases = holdout_cases()
    assert all(c.case_id in HOLDOUT_CASE_IDS for c in cases)
    rows = []
    for case in cases:
        for seed in SEED_MANIFEST:
            forecast = fit_train_forecast(n_scenarios=2, customers_per_scenario=2, seed=seed, announcement_mean=12.0)
            controllers = {
                "b1": FullValidationAlnsMpc(
                    case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=seed
                ),
                "m1": CertificateCarryingAlnsMpc(
                    case.instance, case.horizon, iterations=ALNS_ITER, time_limit_seconds=ALNS_TIME, seed=seed
                ),
                "stochastic_mpc": CommitmentSafePredictiveMpc(
                    case.instance,
                    case.horizon,
                    forecast=forecast,
                    n_scenarios=2,
                    alns_iterations=ALNS_ITER,
                    time_limit_seconds=ALNS_TIME,
                    seed=seed,
                    use_counterfactuals=True,
                    use_forecast=True,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=200,
                ),
                "cce_mpc": CertificateCarryingEconomicMpc(
                    case.instance,
                    case.horizon,
                    forecast=forecast,
                    n_scenarios=2,
                    alns_iterations=ALNS_ITER,
                    time_limit_seconds=ALNS_TIME,
                    seed=seed,
                    use_forecast=True,
                    use_persistent_certificate=True,
                    max_replan_interval=case.max_replan_interval,
                    rollout_max_events=200,
                ),
            }
            cell = {"case_id": case.case_id, "seed": seed, "controllers": {}}
            for name, ctrl in controllers.items():
                res = run_episode(
                    case.instance,
                    case.releases,
                    fleet_size=case.fleet_size,
                    horizon=case.horizon,
                    max_replan_interval=case.max_replan_interval,
                    t_max=case.t_max,
                    controller=ctrl,
                )
                rep = validate_log(case.instance, res.log)
                final = res.final_requests
                cell["controllers"][name] = {
                    "completed_count": sum(1 for st in final.values() if st == "completed"),
                    "accepted_unfulfilled_count": sum(1 for st in final.values() if st == "accepted_unfulfilled"),
                    "rejected_count": sum(1 for st in final.values() if st == "rejected"),
                    "executed_distance": executed_distance_from_log(case.instance, res.log),
                    "optimize_seconds": res.optimize_seconds,
                    "replay_ok": rep.ok,
                    "replay_code": rep.code,
                }
            b1 = cell["controllers"]["b1"]
            cce = cell["controllers"]["cce_mpc"]
            cell["paired"] = {
                "cce_minus_b1_completed": cce["completed_count"] - b1["completed_count"],
                "cce_minus_b1_au": cce["accepted_unfulfilled_count"] - b1["accepted_unfulfilled_count"],
                "valid": cce["replay_ok"] and b1["replay_ok"],
            }
            rows.append(cell)
    valid = [r for r in rows if r["paired"]["valid"]]
    return {
        "holdout_case_ids": list(HOLDOUT_CASE_IDS),
        "seed_manifest": list(SEED_MANIFEST),
        "n_cells": len(rows),
        "n_valid": len(valid),
        "wins_vs_b1": sum(
            1 for r in valid if r["paired"]["cce_minus_b1_completed"] > 0 and r["paired"]["cce_minus_b1_au"] <= 0
        ),
        "losses_vs_b1": sum(
            1 for r in valid if r["paired"]["cce_minus_b1_completed"] < 0 or r["paired"]["cce_minus_b1_au"] > 0
        ),
        "rows": rows,
        "note": "One-shot holdout under frozen protocol; not used for method modification.",
    }


def final_assessment(audit: dict, theorem: dict, ablation: dict, dev: dict, holdout: dict) -> dict:
    accounting_ok = audit["pass_accounting"]
    theorem_ok = theorem["name"] == "ConditionalCertificateValidity" and theorem["supported_by_plant"]
    fac = ablation["factorial"]
    cert_effect = fac["vs_cert_off_forecast_on"]
    vs_m1 = fac["vs_m1"]
    vs_stoch = fac["vs_stochastic_mpc"]
    cert_incremental = (cert_effect.get("n_equal") or 0) >= max(1, (cert_effect.get("n") or 1) // 2) and (
        vs_m1.get("mean_completed_delta_vs_full_cce") is not None
    )
    # Distinct practical certificate benefit?
    cert_benefit = (cert_effect.get("n_better") or 0) > (cert_effect.get("n_worse") or 0) + (
        cert_effect.get("n_equal") or 0
    ) // 2
    predictive_holdout = holdout["wins_vs_b1"] > holdout["losses_vs_b1"] and holdout["wins_vs_b1"] > 0
    predictive_dev = dev.get("wins_vs_b1", 0) > dev.get("losses_vs_b1", 0)

    if not accounting_ok or not theorem_ok:
        label = "UNSUPPORTED_CLAIM"
        reason = "Certificate accounting or mathematical statement still fails integrity checks."
    elif (
        cert_benefit
        and theorem_ok
        and (predictive_dev or predictive_holdout)
        and (vs_stoch.get("n_equal") or 0) < (vs_stoch.get("n") or 1)
    ):
        label = "SUBMISSION_CANDIDATE"
        reason = (
            "Correct conditional theorem, measurable certificate/forecast benefit, and "
            "non-identical outcomes vs stochastic MPC with adequate supporting evidence."
        )
    else:
        label = "INCREMENTAL_RESULT"
        reason = (
            "Technically sound after accounting fixes and a corrected conditional theorem, "
            "but CertificateStore persistence is largely inherited from M1 and/or lacks a "
            "compelling distinct empirical advance over M1 + stochastic MPC."
        )
    return {
        "decision": label,
        "reason": reason,
        "checks": {
            "accounting_ok": accounting_ok,
            "theorem_conditional_ok": theorem_ok,
            "cert_vs_no_cert": cert_effect,
            "cce_vs_m1": vs_m1,
            "cce_vs_stoch": vs_stoch,
            "cert_incremental_signal": cert_incremental,
            "cert_clear_benefit": cert_benefit,
            "dev_wins_vs_b1": dev.get("wins_vs_b1"),
            "holdout_wins_vs_b1": holdout.get("wins_vs_b1"),
            "holdout_losses_vs_b1": holdout.get("losses_vs_b1"),
        },
    }


def run_closeout(*, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or Path("docs/mpc_central")
    paper_dir = Path("docs/paper")
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_dir.mkdir(parents=True, exist_ok=True)

    sha = _git_sha()
    theorem = theorem_document()
    audit = audit_certificate_accounting()
    comparison = source_level_comparison()
    ablation = factorial_ablation()
    # Freeze point recorded in manifest before holdout
    freeze = {
        "frozen_parent_sha_requested": "954ce92099733b2c6beeac9d904615de94a3179a",
        "closeout_worktree_sha_at_run": sha,
        "controller": "CertificateCarryingEconomicMpc",
        "alns_iterations": ALNS_ITER,
        "alns_time_limit_seconds": ALNS_TIME,
        "n_scenarios": 2,
        "seed_manifest": list(SEED_MANIFEST),
        "development_cases": list(FOCUS_CASES),
        "holdout_cases": list(HOLDOUT_CASE_IDS),
        "objective": {
            "SERVICE_REWARD": 100.0,
            "UNFULFILLED_PENALTY": 250.0,
            "DISTANCE_PENALTY": 1.0,
            "tuned_on_wins": False,
        },
        "splits": split_manifest(),
    }
    dev = frozen_development_eval()
    holdout = frozen_holdout_eval()
    assessment = final_assessment(audit, theorem, ablation, dev, holdout)

    audit_doc = {
        "publish_defect": (
            "CertificateStore.publish previously stored observation.accepted only, omitting "
            "newly accepted customers from the same decide() call. Fixed via accepted= post-decision set."
        ),
        "unknown_gap": (
            "UNKNOWN with pending accepted customers is a failure condition of unconditional "
            "invariance; instrumented as obligation_gap and excluded from CERTIFIED claims."
        ),
        "audit_results": audit,
        "theorem": theorem,
        "source_comparison": comparison,
        "ablation": {k: ablation[k] for k in ablation if k != "rows"},
        "assessment_preview": assessment["decision"],
    }
    (out_dir / "FINAL_CERTIFICATE_AUDIT.md").write_text(
        _render_audit_md(audit_doc, assessment),
        encoding="utf-8",
    )
    holdout_path = out_dir / "FROZEN_HOLDOUT_RESULTS.json"
    holdout_artifact = {
        "freeze": freeze,
        "development": {k: dev[k] for k in dev if k != "rows"},
        "development_rows": dev["rows"],
        "holdout": holdout,
        "ablation_summary": ablation["factorial"],
        "assessment": assessment,
    }
    holdout_path.write_text(json.dumps(holdout_artifact, indent=2), encoding="utf-8")

    # Also write reproducibility manifest
    (out_dir / "REPRODUCIBILITY_MANIFEST.json").write_text(
        json.dumps(
            {
                **freeze,
                "commands": [
                    "python -m safe_time_evrp.mpc_central.publication_closeout",
                    "python -m pytest -q",
                ],
                "artifacts": [
                    "docs/mpc_central/FINAL_CERTIFICATE_AUDIT.md",
                    "docs/mpc_central/FROZEN_HOLDOUT_RESULTS.json",
                    "docs/paper/MPC_MANUSCRIPT_FINAL_DRAFT.md",
                    "docs/paper/PUBLICATION_READINESS_REPORT.md",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "freeze": freeze,
        "audit": audit,
        "theorem": theorem,
        "ablation": ablation,
        "development": dev,
        "holdout": holdout,
        "assessment": assessment,
        "comparison": comparison,
    }


def _render_audit_md(doc: dict, assessment: dict) -> str:
    a = doc["audit_results"]
    t = doc["theorem"]
    return f"""# Final certificate audit

## Accounting defect (fixed)

{doc["publish_defect"]}

## UNKNOWN / obligation gap

{doc["unknown_gap"]}

## Regression audit (`A_low_soc_charge`, seed 7)

| Metric | Value |
|--------|------:|
| Certified verify failures | {a["certified_verify_failures"]} |
| Publish accepted mismatches | {a["publish_accepted_mismatches"]} |
| UNKNOWN-with-accepted epochs | {a["unknown_with_accepted"]} |
| Replay ok | {a["replay_ok"]} |
| Accounting pass | {a["pass_accounting"]} |

Gap sample: `{json.dumps(a.get("gap_epochs_sample", [])[:2], indent=2)}`

## Corrected mathematical statement

**{t["name"]}** (replaces withdrawn unconditional NominalCommitmentInvariance)

{t["claim"]}

### Proof

{chr(10).join(f"- {p}" for p in t["proof"])}

### Failure conditions

{chr(10).join(f"- {p}" for p in t["failure_conditions"])}

### Counterexample to the withdrawn claim

{t["counterexample"]}

## Source-level comparison

See structured JSON in the closeout runner output / reproducibility package. M1 and CC-E-MPC share `CertificateStore`.

## Assessment preview

**{assessment["decision"]}** — {assessment["reason"]}
"""


if __name__ == "__main__":
    art = run_closeout()
    print(art["assessment"]["decision"], art["assessment"]["reason"])
    print("audit", art["audit"]["pass_accounting"], "unknown_with_accepted", art["audit"]["unknown_with_accepted"])
    print("holdout", art["holdout"]["wins_vs_b1"], art["holdout"]["losses_vs_b1"])
