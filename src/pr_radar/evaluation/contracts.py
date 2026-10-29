from collections.abc import Mapping
import re
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from pr_radar.contracts import DecisionRecommendation
from pr_radar.contracts import RadarPillarKey
from pr_radar.contracts.base import StrictContract


ExpectedSeverity = Literal["high_risk", "warning", "advisory"]
EvaluationCaseStatus = Literal["evaluated", "unavailable", "invalid"]
MatchOutcome = Literal[
    "matched_expected",
    "missing_expected",
    "unexpected_actual",
    "low_confidence_match",
]

_HASH_VALUE_RE = re.compile(r"^sha256:[A-Za-z0-9_.-]+$")
_HASH_REF_RE = re.compile(r"^[^\s:]+:sha256:[A-Za-z0-9_.-]+$")
_RAW_DIFF_RE = re.compile(r"(?m)^(?:diff --git\b|--- [ab]/|\+\+\+ [ab]/|@@\s+-)")
_RAW_SOURCE_RE = re.compile(
    r"(?m)^\s*(?:async\s+def|def|class|function|const|let|var)\s+[A-Za-z_]\w*",
)
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|token)\s*[:=]\s*"
    r"['\"]?(?!<REDACTED_)[A-Za-z0-9][A-Za-z0-9_.-]{6,}",
)
_INTERNAL_URL_RE = re.compile(
    r"https?://(?:git\.linecorp\.com|ghe\.corp\.yahoo\.co\.jp)(?:/[^\s]*)?",
    re.IGNORECASE,
)


class ExpectedFinding(StrictContract):
    finding_id: str
    pillar: RadarPillarKey
    reason_code: str
    evidence_path: str
    severity: ExpectedSeverity
    source_rule_id: str | None = None
    source_line: int | None = Field(default=None, ge=1)
    source_excerpt_hash: str | None = None
    labels: tuple[str, ...] = ()
    partial_fields: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()

    @field_validator("source_excerpt_hash")
    @classmethod
    def validate_source_excerpt_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _reject_raw_metadata_text(value)
        if not _HASH_VALUE_RE.fullmatch(value):
            raise ValueError("source_excerpt_hash must be a content hash")
        return value


class EvaluationCase(StrictContract):
    case_id: str
    source_format: str
    pr_id: str
    stack: str | None = None
    ruleset_version: str | None = None
    labels: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    expected_findings: tuple[ExpectedFinding, ...] = ()
    partial_fields: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()

    @field_validator("source_refs")
    @classmethod
    def validate_source_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for source_ref in value:
            _reject_raw_metadata_text(source_ref)
            if not _HASH_REF_RE.fullmatch(source_ref):
                raise ValueError("source_refs must be path:sha256:<hash> references")
        return value


class FindingMatchResult(StrictContract):
    outcome: MatchOutcome
    expected_finding_id: str | None = None
    actual_finding_id: str | None = None
    pillar: RadarPillarKey
    reason_code: str
    evidence_path: str | None = None
    match_reason_code: str


class CaseEvaluationResult(StrictContract):
    case_id: str
    status: EvaluationCaseStatus
    match_results: tuple[FindingMatchResult, ...] = ()
    expected_recommendation: DecisionRecommendation | None = None
    actual_recommendation: DecisionRecommendation | None = None
    recommendation_agreement: bool | None = None
    unavailable_reason_code: str | None = None


class MetricsSummary(StrictContract):
    case_count: int = Field(ge=0)
    evaluated_case_count: int = Field(ge=0)
    unavailable_case_count: int = Field(ge=0)
    invalid_case_count: int = Field(ge=0)
    expected_finding_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    low_confidence_match_count: int = Field(ge=0)
    coverage_gap_count: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    recommendation_agreement_rate: float = Field(ge=0.0, le=1.0)


class RunManifest(StrictContract):
    run_id: str
    tool_version: str
    started_at: str
    completed_at: str | None = None
    case_count: int = Field(ge=0)
    ruleset_versions: tuple[str, ...] = ()
    input_hashes: Mapping[str, str] = Field(default_factory=dict, validate_default=True)
    artifact_paths: tuple[str, ...] = ()

    @field_validator("input_hashes", mode="after")
    @classmethod
    def freeze_input_hashes(
        cls,
        input_hashes: Mapping[str, str],
    ) -> Mapping[str, str]:
        for path, digest in input_hashes.items():
            _reject_raw_metadata_text(path)
            _reject_raw_metadata_text(digest)
            if not _HASH_VALUE_RE.fullmatch(digest):
                raise ValueError("input_hashes values must be content hashes")
        return MappingProxyType(dict(input_hashes))

    @field_serializer("input_hashes")
    def serialize_input_hashes(
        self,
        input_hashes: Mapping[str, str],
    ) -> dict[str, str]:
        return dict(input_hashes)


def _reject_raw_metadata_text(value: str) -> None:
    if (
        _RAW_DIFF_RE.search(value)
        or _RAW_SOURCE_RE.search(value)
        or _CREDENTIAL_RE.search(value)
        or _INTERNAL_URL_RE.search(value)
    ):
        raise ValueError("evaluation metadata must be content-free")
