from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pr_radar.contracts import (
    ContextEnvelope,
    ContextEnvelopeItem,
    DecisionReasonCode,
    DecisionRecommendation,
    FindingDecision,
    LOW_CONFIDENCE_TAG,
    PillarDecision,
    PillarDecisionStatus,
    RADAR_PILLARS,
    RiskDecision,
)
from pr_radar.contracts.decisions import (
    BLOCKED_FINDING_PRESENT,
    HIGH_RISK_DEPLOYMENT_DOWNTIME,
    HIGH_RISK_SECURITY_SUPPLY_CHAIN,
    LOW_CONFIDENCE_FINDING_PRESENT,
    NO_MATERIAL_FINDINGS,
    SCORE_THRESHOLD_REACHED,
    WARNING_FINDING_PRESENT,
)


KEV_LOCAL_SCORER_SOURCE = "kev_local_scorer"


def _freeze_reason_mapping(
    mapping: Mapping[str, DecisionReasonCode],
) -> Mapping[str, DecisionReasonCode]:
    return MappingProxyType(dict(mapping))


def _default_high_risk_calibration_reasons() -> Mapping[str, DecisionReasonCode]:
    default_reasons: dict[str, DecisionReasonCode] = {
        "destructive_migration_detected": HIGH_RISK_DEPLOYMENT_DOWNTIME,
        "dependency_added_manifest_requires_review": HIGH_RISK_SECURITY_SUPPLY_CHAIN,
        "dependency_added_manifest_requires_supply_chain_review": (
            HIGH_RISK_SECURITY_SUPPLY_CHAIN
        ),
    }
    return _freeze_reason_mapping(default_reasons)


def _default_high_risk_pillars() -> Mapping[str, DecisionReasonCode]:
    default_pillars: dict[str, DecisionReasonCode] = {
        "deployment_downtime": HIGH_RISK_DEPLOYMENT_DOWNTIME,
        "security_supply_chain": HIGH_RISK_SECURITY_SUPPLY_CHAIN,
    }
    return _freeze_reason_mapping(default_pillars)


@dataclass(frozen=True)
class LocalScorerPolicy:
    request_changes_score_threshold: int = 85
    blocking_finding_statuses: tuple[str, ...] = ("critical", "blocked", "blocker")
    blocking_tags: tuple[str, ...] = ("blocked", "blocker")
    high_risk_finding_statuses: tuple[str, ...] = ("high", "critical")
    high_risk_calibration_reasons: Mapping[str, DecisionReasonCode] = field(
        default_factory=_default_high_risk_calibration_reasons,
    )
    high_risk_pillars: Mapping[str, DecisionReasonCode] = field(
        default_factory=_default_high_risk_pillars,
    )
    low_confidence_tag: str = LOW_CONFIDENCE_TAG
    warning_finding_statuses: tuple[str, ...] = ("warning",)
    reason_priority: tuple[DecisionReasonCode, ...] = (
        SCORE_THRESHOLD_REACHED,
        BLOCKED_FINDING_PRESENT,
        HIGH_RISK_DEPLOYMENT_DOWNTIME,
        HIGH_RISK_SECURITY_SUPPLY_CHAIN,
        LOW_CONFIDENCE_FINDING_PRESENT,
        WARNING_FINDING_PRESENT,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "high_risk_calibration_reasons",
            _freeze_reason_mapping(self.high_risk_calibration_reasons),
        )
        object.__setattr__(
            self,
            "high_risk_pillars",
            _freeze_reason_mapping(self.high_risk_pillars),
        )


@runtime_checkable
class DecisionModelAdapter(Protocol):
    def score(self, context_envelope: ContextEnvelope) -> RiskDecision: ...


class KevLocalScorer:
    def __init__(self, policy: LocalScorerPolicy | None = None) -> None:
        self._policy: LocalScorerPolicy = policy or LocalScorerPolicy()

    def score(self, context_envelope: ContextEnvelope) -> RiskDecision:
        finding_decisions = tuple(
            _score_finding(item, self._policy) for item in context_envelope.items
        )
        primary_reason_codes = _primary_reason_codes(finding_decisions, self._policy)

        return RiskDecision.model_validate(
            {
                "recommendation": _overall_recommendation(primary_reason_codes),
                "overall_score": _overall_score(context_envelope.items),
                "overall_confidence": _overall_confidence(context_envelope.items),
                "decision_source": KEV_LOCAL_SCORER_SOURCE,
                "primary_reason_codes": primary_reason_codes,
                "finding_decisions": finding_decisions,
                "evaluated_pillars": _pillar_decisions(
                    context_envelope.items,
                    finding_decisions,
                ),
                "context_envelope_ref": context_envelope.schema_version,
            },
        )


def _score_finding(
    item: ContextEnvelopeItem,
    policy: LocalScorerPolicy,
) -> FindingDecision:
    reason_codes = _finding_reason_codes(item, policy)
    return FindingDecision.model_validate(
        {
            "finding_id": item.finding_id,
            "recommendation": _finding_recommendation(reason_codes),
            "score": item.score,
            "confidence": item.confidence,
            "reason_codes": reason_codes,
            "evidence_refs": item.evidence_refs,
            "decision_source": KEV_LOCAL_SCORER_SOURCE,
        },
    )


def _finding_reason_codes(
    item: ContextEnvelopeItem,
    policy: LocalScorerPolicy,
) -> tuple[DecisionReasonCode, ...]:
    reason_codes: list[DecisionReasonCode] = []
    if item.score >= policy.request_changes_score_threshold:
        reason_codes.append(SCORE_THRESHOLD_REACHED)
    if _is_blocking_finding(item, policy):
        reason_codes.append(BLOCKED_FINDING_PRESENT)
    high_risk_reason_code = _high_risk_reason_code(item, policy)
    if high_risk_reason_code is not None:
        reason_codes.append(high_risk_reason_code)
    if policy.low_confidence_tag in item.tags:
        reason_codes.append(LOW_CONFIDENCE_FINDING_PRESENT)
    if item.status in policy.warning_finding_statuses:
        reason_codes.append(WARNING_FINDING_PRESENT)
    return tuple(reason_codes)


def _finding_recommendation(
    reason_codes: Sequence[DecisionReasonCode],
) -> DecisionRecommendation:
    if (
        SCORE_THRESHOLD_REACHED in reason_codes
        or BLOCKED_FINDING_PRESENT in reason_codes
    ):
        return "REQUEST_CHANGES"
    if (
        HIGH_RISK_DEPLOYMENT_DOWNTIME in reason_codes
        or HIGH_RISK_SECURITY_SUPPLY_CHAIN in reason_codes
    ):
        return "NEEDS_HUMAN_REVIEW"
    if (
        LOW_CONFIDENCE_FINDING_PRESENT in reason_codes
        or WARNING_FINDING_PRESENT in reason_codes
    ):
        return "APPROVE_WITH_CAUTION"
    return "APPROVE"


def _primary_reason_codes(
    finding_decisions: Sequence[FindingDecision],
    policy: LocalScorerPolicy,
) -> tuple[DecisionReasonCode, ...]:
    reason_codes = {
        reason_code
        for decision in finding_decisions
        for reason_code in decision.reason_codes
    }
    if not reason_codes:
        return (NO_MATERIAL_FINDINGS,)
    return tuple(
        reason_code
        for reason_code in policy.reason_priority
        if reason_code in reason_codes
    )


def _overall_recommendation(
    primary_reason_codes: Sequence[DecisionReasonCode],
) -> DecisionRecommendation:
    if (
        SCORE_THRESHOLD_REACHED in primary_reason_codes
        or BLOCKED_FINDING_PRESENT in primary_reason_codes
    ):
        return "REQUEST_CHANGES"
    if (
        HIGH_RISK_DEPLOYMENT_DOWNTIME in primary_reason_codes
        or HIGH_RISK_SECURITY_SUPPLY_CHAIN in primary_reason_codes
    ):
        return "NEEDS_HUMAN_REVIEW"
    if (
        LOW_CONFIDENCE_FINDING_PRESENT in primary_reason_codes
        or WARNING_FINDING_PRESENT in primary_reason_codes
    ):
        return "APPROVE_WITH_CAUTION"
    return "APPROVE"


def _overall_score(items: Sequence[ContextEnvelopeItem]) -> int:
    if not items:
        return 0
    return max(item.score for item in items)


def _overall_confidence(items: Sequence[ContextEnvelopeItem]) -> float:
    if not items:
        return 1.0
    return min(item.confidence for item in items)


def _pillar_decisions(
    items: Sequence[ContextEnvelopeItem],
    finding_decisions: Sequence[FindingDecision],
) -> dict[str, PillarDecision]:
    decisions_by_finding_id = {
        decision.finding_id: decision for decision in finding_decisions
    }
    decisions: dict[str, PillarDecision] = {}
    pillars = tuple(
        dict.fromkeys(
            (
                *(pillar.key for pillar in RADAR_PILLARS),
                *(item.pillar for item in items),
            ),
        ),
    )
    for pillar in pillars:
        pillar_items = tuple(item for item in items if item.pillar == pillar)
        decisions[pillar] = _pillar_decision(
            pillar,
            pillar_items,
            decisions_by_finding_id,
        )
    return decisions


def _pillar_decision(
    pillar: str,
    items: Sequence[ContextEnvelopeItem],
    decisions_by_finding_id: dict[str, FindingDecision],
) -> PillarDecision:
    if not items:
        return PillarDecision.model_validate(
            {
                "pillar": pillar,
                "status": "not_evaluated",
                "score": 0,
                "confidence": 1.0,
            },
        )

    reason_codes: tuple[DecisionReasonCode, ...] = tuple(
        reason_code
        for item in items
        for reason_code in decisions_by_finding_id[item.finding_id].reason_codes
    )
    return PillarDecision.model_validate(
        {
            "pillar": pillar,
            "status": _pillar_status(reason_codes),
            "score": max(item.score for item in items),
            "confidence": min(item.confidence for item in items),
            "reason_codes": tuple(dict.fromkeys(reason_codes)),
            "evaluated_finding_ids": tuple(item.finding_id for item in items),
        },
    )


def _pillar_status(
    reason_codes: Sequence[DecisionReasonCode],
) -> PillarDecisionStatus:
    if (
        SCORE_THRESHOLD_REACHED in reason_codes
        or BLOCKED_FINDING_PRESENT in reason_codes
    ):
        return "blocked"
    if (
        HIGH_RISK_DEPLOYMENT_DOWNTIME in reason_codes
        or HIGH_RISK_SECURITY_SUPPLY_CHAIN in reason_codes
    ):
        return "high_risk"
    if (
        LOW_CONFIDENCE_FINDING_PRESENT in reason_codes
        or WARNING_FINDING_PRESENT in reason_codes
    ):
        return "warning"
    return "no_findings"


def _is_blocking_finding(
    item: ContextEnvelopeItem,
    policy: LocalScorerPolicy,
) -> bool:
    return (
        item.status in policy.blocking_finding_statuses
        or bool(set(item.tags).intersection(policy.blocking_tags))
    )


def _high_risk_reason_code(
    item: ContextEnvelopeItem,
    policy: LocalScorerPolicy,
) -> DecisionReasonCode | None:
    calibration_reason = item.calibration_reason
    if (
        calibration_reason is not None
        and calibration_reason in policy.high_risk_calibration_reasons
    ):
        return policy.high_risk_calibration_reasons[calibration_reason]
    if (
        item.status in policy.high_risk_finding_statuses
        and item.pillar in policy.high_risk_pillars
    ):
        return policy.high_risk_pillars[item.pillar]
    return None
