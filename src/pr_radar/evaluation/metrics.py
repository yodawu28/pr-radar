from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from pydantic import Field, field_serializer, field_validator

from pr_radar.contracts import RadarPillarKey
from pr_radar.contracts.base import StrictContract
from pr_radar.evaluation.contracts import (
    CaseEvaluationResult,
    FindingMatchResult,
    MetricsSummary,
)


PillarReasonKey = tuple[RadarPillarKey, str]


class EvaluationMetricsReport(StrictContract):
    overall: MetricsSummary
    by_pillar_reason: Mapping[PillarReasonKey, MetricsSummary] = Field(
        default_factory=dict,
        validate_default=True,
    )
    coverage_gaps_by_reason: Mapping[str, int] = Field(
        default_factory=dict,
        validate_default=True,
    )

    @field_validator("by_pillar_reason", mode="after")
    @classmethod
    def freeze_by_pillar_reason(
        cls,
        value: Mapping[PillarReasonKey, MetricsSummary],
    ) -> Mapping[PillarReasonKey, MetricsSummary]:
        return MappingProxyType(dict(value))

    @field_validator("coverage_gaps_by_reason", mode="after")
    @classmethod
    def freeze_coverage_gaps_by_reason(
        cls,
        value: Mapping[str, int],
    ) -> Mapping[str, int]:
        return MappingProxyType(dict(value))

    @field_serializer("by_pillar_reason")
    def serialize_by_pillar_reason(
        self,
        value: Mapping[PillarReasonKey, MetricsSummary],
    ) -> dict[str, MetricsSummary]:
        return {f"{pillar}:{reason_code}": metrics for (pillar, reason_code), metrics in value.items()}

    @field_serializer("coverage_gaps_by_reason")
    def serialize_coverage_gaps_by_reason(
        self,
        value: Mapping[str, int],
    ) -> dict[str, int]:
        return dict(value)


def summarize_metrics(
    *,
    case_results: Iterable[CaseEvaluationResult],
) -> EvaluationMetricsReport:
    """Aggregate baseline evaluation metrics without enforcing quality gates."""
    cases = tuple(case_results)
    overall_counts = _Counts()
    by_pillar_reason_counts: defaultdict[PillarReasonKey, _Counts] = defaultdict(_Counts)
    coverage_gaps_by_reason: Counter[str] = Counter()
    recommendation_evaluable_count = 0
    recommendation_agreement_count = 0

    for case_result in cases:
        if case_result.status == "evaluated":
            overall_counts.evaluated_case_count += 1
            recommendation_evaluable_count += _has_recommendation_signal(case_result)
            recommendation_agreement_count += _recommendation_agreement_value(case_result)
            _record_match_results(
                case_result.match_results,
                overall_counts=overall_counts,
                by_pillar_reason_counts=by_pillar_reason_counts,
            )
            continue

        if case_result.status == "unavailable":
            overall_counts.unavailable_case_count += 1
        elif case_result.status == "invalid":
            overall_counts.invalid_case_count += 1

        overall_counts.coverage_gap_count += 1
        reason_code = case_result.unavailable_reason_code or case_result.status
        coverage_gaps_by_reason[reason_code] += 1

    overall = _to_metrics_summary(
        overall_counts,
        case_count=len(cases),
        recommendation_agreement_rate=_safe_ratio(
            recommendation_agreement_count,
            recommendation_evaluable_count,
        ),
    )
    by_pillar_reason = {
        key: _to_metrics_summary(
            counts,
            case_count=0,
            recommendation_agreement_rate=0.0,
        )
        for key, counts in sorted(by_pillar_reason_counts.items())
    }

    return EvaluationMetricsReport(
        overall=overall,
        by_pillar_reason=by_pillar_reason,
        coverage_gaps_by_reason=dict(sorted(coverage_gaps_by_reason.items())),
    )


class _Counts:
    def __init__(self) -> None:
        self.evaluated_case_count = 0
        self.unavailable_case_count = 0
        self.invalid_case_count = 0
        self.expected_finding_count = 0
        self.true_positive_count = 0
        self.false_positive_count = 0
        self.false_negative_count = 0
        self.low_confidence_match_count = 0
        self.coverage_gap_count = 0


def _record_match_results(
    match_results: Iterable[FindingMatchResult],
    *,
    overall_counts: _Counts,
    by_pillar_reason_counts: defaultdict[PillarReasonKey, _Counts],
) -> None:
    for match_result in match_results:
        pillar_reason_key = (match_result.pillar, match_result.reason_code)
        key_counts = by_pillar_reason_counts[pillar_reason_key]
        if match_result.outcome == "matched_expected":
            _record_expected_finding(overall_counts)
            _record_expected_finding(key_counts)
            overall_counts.true_positive_count += 1
            key_counts.true_positive_count += 1
        elif match_result.outcome == "unexpected_actual":
            overall_counts.false_positive_count += 1
            key_counts.false_positive_count += 1
        elif match_result.outcome == "missing_expected":
            _record_expected_finding(overall_counts)
            _record_expected_finding(key_counts)
            overall_counts.false_negative_count += 1
            key_counts.false_negative_count += 1
        elif match_result.outcome == "low_confidence_match":
            _record_expected_finding(overall_counts)
            _record_expected_finding(key_counts)
            overall_counts.low_confidence_match_count += 1
            key_counts.low_confidence_match_count += 1


def _record_expected_finding(counts: _Counts) -> None:
    counts.expected_finding_count += 1


def _has_recommendation_signal(case_result: CaseEvaluationResult) -> int:
    return int(
        case_result.expected_recommendation is not None
        and case_result.actual_recommendation is not None
        and case_result.recommendation_agreement is not None,
    )


def _recommendation_agreement_value(case_result: CaseEvaluationResult) -> int:
    if not _has_recommendation_signal(case_result):
        return 0
    return int(case_result.recommendation_agreement is True)


def _to_metrics_summary(
    counts: _Counts,
    *,
    case_count: int,
    recommendation_agreement_rate: float,
) -> MetricsSummary:
    return MetricsSummary(
        case_count=case_count,
        evaluated_case_count=counts.evaluated_case_count,
        unavailable_case_count=counts.unavailable_case_count,
        invalid_case_count=counts.invalid_case_count,
        expected_finding_count=counts.expected_finding_count,
        true_positive_count=counts.true_positive_count,
        false_positive_count=counts.false_positive_count,
        false_negative_count=counts.false_negative_count,
        low_confidence_match_count=counts.low_confidence_match_count,
        coverage_gap_count=counts.coverage_gap_count,
        precision=_safe_ratio(
            counts.true_positive_count,
            counts.true_positive_count + counts.false_positive_count,
        ),
        recall=_safe_ratio(
            counts.true_positive_count,
            counts.true_positive_count + counts.false_negative_count,
        ),
        recommendation_agreement_rate=recommendation_agreement_rate,
    )


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
