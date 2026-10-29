from importlib import import_module

import pytest

from pr_radar.contracts import DecisionRecommendation, RadarPillarKey
from pr_radar.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCaseStatus,
    FindingMatchResult,
    MatchOutcome,
)


def _metrics_module():
    try:
        module = import_module("pr_radar.evaluation.metrics")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.metrics: {error}")

    assert hasattr(module, "summarize_metrics"), (
        "expected pr_radar.evaluation.metrics.summarize_metrics"
    )
    return module


def _match(
    *,
    outcome: MatchOutcome,
    pillar: RadarPillarKey = "security_supply_chain",
    reason_code: str = "dependency_added_manifest_requires_supply_chain_review",
    expected_finding_id: str | None = "expected:dependency.added",
    actual_finding_id: str | None = "dependency.added.pyproject",
    evidence_path: str | None = "pyproject.toml",
    match_reason_code: str = "pillar_reason_path_match",
) -> FindingMatchResult:
    return FindingMatchResult(
        outcome=outcome,
        expected_finding_id=expected_finding_id,
        actual_finding_id=actual_finding_id,
        pillar=pillar,
        reason_code=reason_code,
        evidence_path=evidence_path,
        match_reason_code=match_reason_code,
    )


def _case(
    *,
    case_id: str = "case-001",
    status: EvaluationCaseStatus = "evaluated",
    match_results: tuple[FindingMatchResult, ...] = (),
    expected_recommendation: DecisionRecommendation | None = None,
    actual_recommendation: DecisionRecommendation | None = None,
    recommendation_agreement: bool | None = None,
    unavailable_reason_code: str | None = None,
) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case_id,
        status=status,
        match_results=match_results,
        expected_recommendation=expected_recommendation,
        actual_recommendation=actual_recommendation,
        recommendation_agreement=recommendation_agreement,
        unavailable_reason_code=unavailable_reason_code,
    )


def test_summarizes_precision_recall_by_pillar_reason_key() -> None:
    """Locks primary Sprint 5 precision/recall at the finding vocabulary unit."""
    metrics = _metrics_module()

    report = metrics.summarize_metrics(
        case_results=(
            _case(
                match_results=(
                    _match(outcome="matched_expected"),
                    _match(
                        outcome="unexpected_actual",
                        expected_finding_id=None,
                        actual_finding_id="dependency.added.package_json",
                    ),
                    _match(
                        outcome="missing_expected",
                        pillar="deployment_downtime",
                        reason_code="destructive_migration_data_loss_risk",
                        expected_finding_id="expected:migration.destructive",
                        actual_finding_id=None,
                        evidence_path="db/migrate/001_drop_column.sql",
                        match_reason_code="no_actual_match",
                    ),
                ),
            ),
        ),
    )

    assert report.overall.case_count == 1
    assert report.overall.evaluated_case_count == 1
    assert report.overall.true_positive_count == 1
    assert report.overall.false_positive_count == 1
    assert report.overall.false_negative_count == 1
    assert report.overall.precision == 0.5
    assert report.overall.recall == 0.5

    dependency_metrics = report.by_pillar_reason[
        (
            "security_supply_chain",
            "dependency_added_manifest_requires_supply_chain_review",
        )
    ]
    assert dependency_metrics.true_positive_count == 1
    assert dependency_metrics.false_positive_count == 1
    assert dependency_metrics.false_negative_count == 0
    assert dependency_metrics.precision == 0.5
    assert dependency_metrics.recall == 1.0

    migration_metrics = report.by_pillar_reason[
        ("deployment_downtime", "destructive_migration_data_loss_risk")
    ]
    assert migration_metrics.true_positive_count == 0
    assert migration_metrics.false_positive_count == 0
    assert migration_metrics.false_negative_count == 1
    assert migration_metrics.precision == 0.0
    assert migration_metrics.recall == 0.0


def test_summarizes_recommendation_agreement_for_evaluated_cases_only() -> None:
    """Unavailable cases must not dilute recommendation agreement."""
    metrics = _metrics_module()

    report = metrics.summarize_metrics(
        case_results=(
            _case(
                case_id="case-agree",
                expected_recommendation="APPROVE_WITH_CAUTION",
                actual_recommendation="APPROVE_WITH_CAUTION",
                recommendation_agreement=True,
            ),
            _case(
                case_id="case-disagree",
                expected_recommendation="REQUEST_CHANGES",
                actual_recommendation="NEEDS_HUMAN_REVIEW",
                recommendation_agreement=False,
            ),
            _case(
                case_id="case-unavailable",
                status="unavailable",
                unavailable_reason_code="missing_local_workspace",
            ),
        ),
    )

    assert report.overall.case_count == 3
    assert report.overall.evaluated_case_count == 2
    assert report.overall.unavailable_case_count == 1
    assert report.overall.recommendation_agreement_rate == 0.5


def test_separates_low_confidence_matches_from_primary_precision() -> None:
    """Low-confidence hits are visible but do not count as primary TP/FP/FN."""
    metrics = _metrics_module()

    report = metrics.summarize_metrics(
        case_results=(
            _case(
                match_results=(
                    _match(outcome="matched_expected"),
                    _match(
                        outcome="low_confidence_match",
                        pillar="test_integrity",
                        reason_code="behavior_change_without_test_evidence_low_confidence",
                        expected_finding_id="expected:test_shape.missing_behavior",
                        actual_finding_id="test_shape.missing_behavior_coverage",
                        evidence_path="src/orders/service.py",
                        match_reason_code="low_confidence_match",
                    ),
                    _match(
                        outcome="unexpected_actual",
                        expected_finding_id=None,
                        actual_finding_id="dependency.added.package_json",
                    ),
                ),
            ),
        ),
    )

    assert report.overall.expected_finding_count == 2
    assert report.overall.true_positive_count == 1
    assert report.overall.false_positive_count == 1
    assert report.overall.false_negative_count == 0
    assert report.overall.low_confidence_match_count == 1
    assert report.overall.precision == 0.5
    assert report.overall.recall == 1.0


def test_reports_coverage_gaps_for_unavailable_and_invalid_cases() -> None:
    """Unavailable/invalid cases are coverage gaps, not false negatives."""
    metrics = _metrics_module()

    report = metrics.summarize_metrics(
        case_results=(
            _case(
                case_id="case-unavailable",
                status="unavailable",
                unavailable_reason_code="missing_local_workspace",
            ),
            _case(
                case_id="case-invalid",
                status="invalid",
                unavailable_reason_code="invalid_manifest_schema",
            ),
        ),
    )

    assert report.overall.case_count == 2
    assert report.overall.evaluated_case_count == 0
    assert report.overall.unavailable_case_count == 1
    assert report.overall.invalid_case_count == 1
    assert report.overall.coverage_gap_count == 2
    assert report.overall.false_negative_count == 0
    assert report.coverage_gaps_by_reason == {
        "invalid_manifest_schema": 1,
        "missing_local_workspace": 1,
    }


def test_empty_suite_metrics_avoid_zero_division() -> None:
    """Baseline runs with no cases must report explicit zero metrics."""
    metrics = _metrics_module()

    report = metrics.summarize_metrics(case_results=())

    assert report.overall.case_count == 0
    assert report.overall.evaluated_case_count == 0
    assert report.overall.expected_finding_count == 0
    assert report.overall.precision == 0.0
    assert report.overall.recall == 0.0
    assert report.overall.recommendation_agreement_rate == 0.0
    assert report.by_pillar_reason == {}
    assert report.coverage_gaps_by_reason == {}
