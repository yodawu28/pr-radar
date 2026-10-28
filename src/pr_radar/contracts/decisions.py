from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from pr_radar.contracts.base import StrictContract


DecisionStatus = Literal["safe", "needs_attention", "high_risk", "blocker"]
DecisionRecommendation = Literal[
    "APPROVE",
    "APPROVE_WITH_CAUTION",
    "NEEDS_HUMAN_REVIEW",
    "REQUEST_CHANGES",
]
PillarDecisionStatus = Literal[
    "not_evaluated",
    "no_findings",
    "warning",
    "high_risk",
    "blocked",
    "unavailable",
]
DecisionSource = Literal[
    "deterministic",
    "kev_local",
    "kev_local_scorer",
    "hosted_llm",
    "unavailable",
]
DecisionReasonCode = Literal[
    "SCORE_THRESHOLD_REACHED",
    "BLOCKED_FINDING_PRESENT",
    "HIGH_RISK_DEPLOYMENT_DOWNTIME",
    "HIGH_RISK_SECURITY_SUPPLY_CHAIN",
    "LOW_CONFIDENCE_FINDING_PRESENT",
    "WARNING_FINDING_PRESENT",
    "NO_MATERIAL_FINDINGS",
    "DECISION_SCORER_UNAVAILABLE",
    "DECISION_CONTEXT_MISSING",
    "DECISION_CONTEXT_BUDGET_EXCEEDED",
]

SCORE_THRESHOLD_REACHED: DecisionReasonCode = "SCORE_THRESHOLD_REACHED"
BLOCKED_FINDING_PRESENT: DecisionReasonCode = "BLOCKED_FINDING_PRESENT"
HIGH_RISK_DEPLOYMENT_DOWNTIME: DecisionReasonCode = (
    "HIGH_RISK_DEPLOYMENT_DOWNTIME"
)
HIGH_RISK_SECURITY_SUPPLY_CHAIN: DecisionReasonCode = (
    "HIGH_RISK_SECURITY_SUPPLY_CHAIN"
)
LOW_CONFIDENCE_FINDING_PRESENT: DecisionReasonCode = (
    "LOW_CONFIDENCE_FINDING_PRESENT"
)
WARNING_FINDING_PRESENT: DecisionReasonCode = "WARNING_FINDING_PRESENT"
NO_MATERIAL_FINDINGS: DecisionReasonCode = "NO_MATERIAL_FINDINGS"
DECISION_SCORER_UNAVAILABLE: DecisionReasonCode = "DECISION_SCORER_UNAVAILABLE"
DECISION_CONTEXT_MISSING: DecisionReasonCode = "DECISION_CONTEXT_MISSING"
DECISION_CONTEXT_BUDGET_EXCEEDED: DecisionReasonCode = (
    "DECISION_CONTEXT_BUDGET_EXCEEDED"
)

DECISION_REASON_CODES: tuple[DecisionReasonCode, ...] = (
    SCORE_THRESHOLD_REACHED,
    BLOCKED_FINDING_PRESENT,
    HIGH_RISK_DEPLOYMENT_DOWNTIME,
    HIGH_RISK_SECURITY_SUPPLY_CHAIN,
    LOW_CONFIDENCE_FINDING_PRESENT,
    WARNING_FINDING_PRESENT,
    NO_MATERIAL_FINDINGS,
    DECISION_SCORER_UNAVAILABLE,
    DECISION_CONTEXT_MISSING,
    DECISION_CONTEXT_BUDGET_EXCEEDED,
)


class Decision(StrictContract):
    status: DecisionStatus
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()
    decision_source: DecisionSource


class FindingDecision(StrictContract):
    finding_id: str
    recommendation: DecisionRecommendation
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[DecisionReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    decision_source: DecisionSource


class PillarDecision(StrictContract):
    pillar: str
    status: PillarDecisionStatus
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[DecisionReasonCode, ...] = ()
    evaluated_finding_ids: tuple[str, ...] = ()


class RiskDecision(StrictContract):
    recommendation: DecisionRecommendation
    overall_score: int = Field(ge=0, le=100)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    decision_source: DecisionSource
    primary_reason_codes: tuple[DecisionReasonCode, ...] = ()
    finding_decisions: tuple[FindingDecision, ...] = ()
    evaluated_pillars: Mapping[str, PillarDecision] = Field(
        default_factory=dict,
        validate_default=True,
    )
    context_envelope_ref: str | None = None

    @field_validator("evaluated_pillars", mode="after")
    @classmethod
    def freeze_evaluated_pillars(
        cls,
        evaluated_pillars: Mapping[str, PillarDecision],
    ) -> Mapping[str, PillarDecision]:
        return MappingProxyType(dict(evaluated_pillars))

    @field_serializer("evaluated_pillars")
    def serialize_evaluated_pillars(
        self,
        evaluated_pillars: Mapping[str, PillarDecision],
    ) -> dict[str, PillarDecision]:
        return dict(evaluated_pillars)
