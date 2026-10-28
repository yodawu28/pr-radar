from collections.abc import Sequence

from pr_radar.contracts import (
    ContextEnvelope,
    ContextEnvelopeItem,
    DecisionReasonCode,
    FindingDecision,
    PillarDecision,
    RADAR_PILLARS,
    RiskDecision,
)
from pr_radar.contracts.decisions import (
    DECISION_CONTEXT_BUDGET_EXCEEDED,
    DECISION_CONTEXT_MISSING,
    DECISION_SCORER_UNAVAILABLE,
)
from pr_radar.review.context_guard import validate_decision_context
from pr_radar.review.local_scorer import DecisionModelAdapter, KevLocalScorer


def evaluate_risk_decision(
    context_envelope: ContextEnvelope | None,
    *,
    scorer: DecisionModelAdapter | None = None,
) -> RiskDecision:
    if context_envelope is None:
        return _unavailable_decision(reason_code=DECISION_CONTEXT_MISSING)

    if context_envelope.budget.is_over_budget:
        return _unavailable_decision(
            reason_code=DECISION_CONTEXT_BUDGET_EXCEEDED,
            context_envelope=context_envelope,
        )

    validate_decision_context(context_envelope)
    active_scorer = scorer or KevLocalScorer()
    try:
        return active_scorer.score(context_envelope)
    except Exception:
        return _unavailable_decision(
            reason_code=DECISION_SCORER_UNAVAILABLE,
            context_envelope=context_envelope,
        )


def _unavailable_decision(
    *,
    reason_code: DecisionReasonCode,
    context_envelope: ContextEnvelope | None = None,
) -> RiskDecision:
    items = context_envelope.items if context_envelope is not None else ()
    finding_decisions = tuple(
        _unavailable_finding_decision(item, reason_code) for item in items
    )
    return RiskDecision.model_validate(
        {
            "recommendation": "NEEDS_HUMAN_REVIEW",
            "overall_score": _max_score(items),
            "overall_confidence": 0.0,
            "decision_source": "unavailable",
            "primary_reason_codes": (reason_code,),
            "finding_decisions": finding_decisions,
            "evaluated_pillars": _unavailable_pillar_decisions(
                items,
                reason_code,
            ),
            "context_envelope_ref": (
                context_envelope.schema_version
                if context_envelope is not None
                else None
            ),
        },
    )


def _unavailable_finding_decision(
    item: ContextEnvelopeItem,
    reason_code: DecisionReasonCode,
) -> FindingDecision:
    return FindingDecision.model_validate(
        {
            "finding_id": item.finding_id,
            "recommendation": "NEEDS_HUMAN_REVIEW",
            "score": item.score,
            "confidence": item.confidence,
            "reason_codes": (reason_code,),
            "evidence_refs": item.evidence_refs,
            "decision_source": "unavailable",
        },
    )


def _unavailable_pillar_decisions(
    items: Sequence[ContextEnvelopeItem],
    reason_code: DecisionReasonCode,
) -> dict[str, PillarDecision]:
    pillars = tuple(
        dict.fromkeys(
            (
                *(pillar.key for pillar in RADAR_PILLARS),
                *(item.pillar for item in items),
            ),
        ),
    )
    return {
        pillar: _unavailable_pillar_decision(
            pillar,
            tuple(item for item in items if item.pillar == pillar),
            reason_code,
        )
        for pillar in pillars
    }


def _unavailable_pillar_decision(
    pillar: str,
    items: Sequence[ContextEnvelopeItem],
    reason_code: DecisionReasonCode,
) -> PillarDecision:
    return PillarDecision.model_validate(
        {
            "pillar": pillar,
            "status": "unavailable",
            "score": _max_score(items),
            "confidence": 0.0,
            "reason_codes": (reason_code,),
            "evaluated_finding_ids": tuple(item.finding_id for item in items),
        },
    )


def _max_score(items: Sequence[ContextEnvelopeItem]) -> int:
    if not items:
        return 0
    return max(item.score for item in items)
