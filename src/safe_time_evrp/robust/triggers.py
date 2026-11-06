"""Replanning triggers.

Validity-aware triggering is not a claim that slack creates safety. If the backup
is already certified and its hypotheses are unchanged, skipping economic
reoptimization does not remove that certificate. New requests are still decided
immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.robust.certificate import Certificate


class TriggerPolicy(str, Enum):
    FIXED_PERIOD = "fixed_period"
    EVERY_EVENT = "every_event"
    SLACK_HEURISTIC = "slack_heuristic"
    VALIDITY_AWARE = "validity_aware"


_HYPOTHESIS = {"bound_update", "soc_discrepancy", "disruption"}
_PROMPT = {"request_release", "initial"}


@dataclass(frozen=True)
class TriggerDecision:
    optimize: bool
    reason: str
    safety_related: bool


def classify(
    policy: TriggerPolicy,
    event_kind: str,
    certificate: Certificate | None,
    *,
    slack_time: float = 5.0,
    slack_energy: float = 1.0,
    ignore_requests: bool = False,
) -> TriggerDecision:
    if event_kind in _PROMPT and not ignore_requests:
        return TriggerDecision(True, "prompt_acceptance", True)
    if event_kind in _HYPOTHESIS:
        return TriggerDecision(True, "certificate_hypothesis_changed", True)
    if policy is TriggerPolicy.EVERY_EVENT:
        return TriggerDecision(True, "every_event", False)
    if policy is TriggerPolicy.FIXED_PERIOD:
        if event_kind == "replan_interval":
            return TriggerDecision(True, "fixed_period", False)
        return TriggerDecision(False, "waiting_for_period", False)
    if policy is TriggerPolicy.SLACK_HEURISTIC:
        if certificate is None:
            return TriggerDecision(True, "heuristic_missing_certificate", False)
        time_margin = certificate.time_margin if certificate.time_margin is not None else 0.0
        energy_margin = certificate.energy_margin if certificate.energy_margin is not None else 0.0
        if time_margin < slack_time or energy_margin < slack_energy:
            return TriggerDecision(True, "heuristic_low_slack", False)
        return TriggerDecision(False, "heuristic_slack_sufficient", False)
    if policy is TriggerPolicy.VALIDITY_AWARE:
        return TriggerDecision(False, "backup_hypotheses_unchanged", False)
    raise ValueError(f"unknown trigger policy {policy}")
