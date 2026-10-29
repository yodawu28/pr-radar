from collections.abc import Callable, Sequence
from pathlib import Path
import re

from pr_radar.contracts import DecisionRecommendation, Report
from pr_radar.contracts.base import StrictContract
from pr_radar.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    ExpectedFinding,
)
from pr_radar.evaluation.manifest_loader import (
    EvaluationManifestLoadError,
    load_evaluation_manifest,
)
from pr_radar.evaluation.matcher import RuleIdMapping, match_findings
from pr_radar.evaluation.metrics import EvaluationMetricsReport, summarize_metrics


ScanEvaluationCase = Callable[[EvaluationCase], Report]
_UNAVAILABLE_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class EvaluationCaseUnavailable(RuntimeError):
    """Raised by scan adapters for known per-case evaluation gaps."""

    def __init__(self, reason_code: str) -> None:
        _validate_unavailable_reason_code(reason_code)
        super().__init__(reason_code)
        self.reason_code = reason_code


class EvaluationRunResult(StrictContract):
    case_results: tuple[CaseEvaluationResult, ...]
    metrics: EvaluationMetricsReport


def run_evaluation_cases(
    *,
    cases: Sequence[EvaluationCase],
    scan_case: ScanEvaluationCase,
    rule_id_mapping: RuleIdMapping | None = None,
) -> EvaluationRunResult:
    case_results: list[CaseEvaluationResult] = []

    for evaluation_case in cases:
        try:
            report = scan_case(evaluation_case)
        except EvaluationCaseUnavailable as error:
            case_results.append(_unavailable_result(evaluation_case, error.reason_code))
            continue

        case_results.append(
            _evaluated_result(
                evaluation_case=evaluation_case,
                report=report,
                rule_id_mapping=rule_id_mapping,
            ),
        )

    results = tuple(case_results)
    return EvaluationRunResult(
        case_results=results,
        metrics=summarize_metrics(case_results=results),
    )


def run_evaluation_suite_or_exit(
    manifest_path: str | Path,
    *,
    scan_case: ScanEvaluationCase,
    rule_id_mapping: RuleIdMapping | None = None,
) -> EvaluationRunResult:
    try:
        cases = load_evaluation_manifest(manifest_path)
    except EvaluationManifestLoadError as error:
        raise SystemExit(2) from error

    return run_evaluation_cases(
        cases=cases,
        scan_case=scan_case,
        rule_id_mapping=rule_id_mapping,
    )


def _evaluated_result(
    *,
    evaluation_case: EvaluationCase,
    report: Report,
    rule_id_mapping: RuleIdMapping | None,
) -> CaseEvaluationResult:
    expected_recommendation = _expected_recommendation(
        evaluation_case.expected_findings,
    )
    actual_recommendation = (
        report.risk_decision.recommendation
        if report.risk_decision is not None
        else None
    )
    return CaseEvaluationResult(
        case_id=evaluation_case.case_id,
        status="evaluated",
        match_results=match_findings(
            expected_findings=evaluation_case.expected_findings,
            actual_findings=report.findings,
            rule_id_mapping=rule_id_mapping,
        ),
        expected_recommendation=expected_recommendation,
        actual_recommendation=actual_recommendation,
        recommendation_agreement=_recommendation_agreement(
            expected_recommendation,
            actual_recommendation,
        ),
    )


def _unavailable_result(
    evaluation_case: EvaluationCase,
    reason_code: str,
) -> CaseEvaluationResult:
    _validate_unavailable_reason_code(reason_code)
    return CaseEvaluationResult(
        case_id=evaluation_case.case_id,
        status="unavailable",
        unavailable_reason_code=reason_code,
    )


def _expected_recommendation(
    expected_findings: Sequence[ExpectedFinding],
) -> DecisionRecommendation:
    severities = {expected.severity for expected in expected_findings}
    if "high_risk" in severities:
        return "REQUEST_CHANGES"
    if "warning" in severities:
        return "APPROVE_WITH_CAUTION"
    return "APPROVE"


def _recommendation_agreement(
    expected_recommendation: DecisionRecommendation,
    actual_recommendation: DecisionRecommendation | None,
) -> bool | None:
    if actual_recommendation is None:
        return None
    return expected_recommendation == actual_recommendation


def _validate_unavailable_reason_code(reason_code: str) -> None:
    if not _UNAVAILABLE_REASON_CODE_RE.fullmatch(reason_code):
        raise ValueError("unavailable reason code must be a machine token")
