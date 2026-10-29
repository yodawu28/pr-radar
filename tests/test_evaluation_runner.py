from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from pr_radar.contracts import Finding, PrInput, Report, RiskDecision
from pr_radar.evaluation.contracts import EvaluationCase, ExpectedFinding


def _runner_module() -> Any:
    try:
        module = import_module("pr_radar.evaluation.runner")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.runner: {error}")

    assert hasattr(module, "run_evaluation_cases"), (
        "expected pr_radar.evaluation.runner.run_evaluation_cases"
    )
    assert hasattr(module, "run_evaluation_suite_or_exit"), (
        "expected pr_radar.evaluation.runner.run_evaluation_suite_or_exit"
    )
    assert hasattr(module, "EvaluationCaseUnavailable"), (
        "expected pr_radar.evaluation.runner.EvaluationCaseUnavailable"
    )
    return module


def _case(
    *,
    case_id: str = "case-source-present",
    expected_findings: tuple[ExpectedFinding, ...] | None = None,
) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        source_format="synthetic_replay",
        pr_id="github:example/repo#17",
        stack="python",
        source_refs=("ground_truth.json:sha256:case001",),
        expected_findings=expected_findings
        or (
            ExpectedFinding(
                finding_id="expected:dependency.added.pyproject",
                pillar="security_supply_chain",
                reason_code="dependency_added_manifest_requires_supply_chain_review",
                evidence_path="pyproject.toml",
                severity="high_risk",
            ),
        ),
    )


def _report(
    *,
    finding: Finding | None = None,
    recommendation: str = "REQUEST_CHANGES",
) -> Report:
    finding = finding or Finding(
        id="dependency.added.pyproject",
        pillar="security_supply_chain",
        title="Dependency manifest changed",
        status="high",
        score=88,
        confidence=0.86,
        evidence_refs=("file:pyproject.toml", "diff:pyproject.toml"),
        decision_source="deterministic",
        calibration_reason="dependency_added_manifest_requires_supply_chain_review",
    )
    return Report(
        overall_status="high_risk",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="No AI-generation evidence detected in replay.",
        findings=(finding,),
        risk_decision=RiskDecision(
            recommendation=recommendation,  # type: ignore[arg-type]
            overall_score=90,
            overall_confidence=0.9,
            decision_source="kev_local_scorer",
            primary_reason_codes=("HIGH_RISK_SECURITY_SUPPLY_CHAIN",),
        ),
    )


def test_runner_evaluates_source_present_replay_case_from_scan_output() -> None:
    """Locks runner orchestration around source-present/replay scan reports."""
    runner = _runner_module()
    evaluation_case = _case()

    def scan_case(case: EvaluationCase) -> Report:
        assert case.case_id == "case-source-present"
        return _report()

    result = runner.run_evaluation_cases(
        cases=(evaluation_case,),
        scan_case=scan_case,
    )

    assert result.metrics.overall.case_count == 1
    assert result.metrics.overall.evaluated_case_count == 1
    assert result.metrics.overall.true_positive_count == 1
    assert result.metrics.overall.precision == 1.0
    assert result.metrics.overall.recall == 1.0
    assert result.metrics.overall.recommendation_agreement_rate == 1.0

    case_result = result.case_results[0]
    assert case_result.case_id == "case-source-present"
    assert case_result.status == "evaluated"
    assert case_result.expected_recommendation == "REQUEST_CHANGES"
    assert case_result.actual_recommendation == "REQUEST_CHANGES"
    assert case_result.recommendation_agreement is True
    assert [(match.outcome, match.match_reason_code) for match in case_result.match_results] == [
        ("matched_expected", "pillar_reason_path_match"),
    ]


def test_runner_degrades_case_level_unavailable_errors_and_continues() -> None:
    """Auth/network/missing-workspace failures are case outcomes, not suite crashes."""
    runner = _runner_module()
    unavailable_case = _case(case_id="case-missing-workspace")
    evaluated_case = _case(case_id="case-evaluated")

    def scan_case(case: EvaluationCase) -> Report:
        if case.case_id == "case-missing-workspace":
            raise runner.EvaluationCaseUnavailable("missing_local_workspace")
        return _report()

    result = runner.run_evaluation_cases(
        cases=(unavailable_case, evaluated_case),
        scan_case=scan_case,
    )

    assert [case_result.status for case_result in result.case_results] == [
        "unavailable",
        "evaluated",
    ]
    assert result.case_results[0].unavailable_reason_code == "missing_local_workspace"
    assert result.metrics.overall.case_count == 2
    assert result.metrics.overall.unavailable_case_count == 1
    assert result.metrics.overall.evaluated_case_count == 1
    assert result.metrics.coverage_gaps_by_reason == {
        "missing_local_workspace": 1,
    }


def test_runner_rejects_raw_or_secret_unavailable_reason_codes() -> None:
    """Unavailable reasons are future artifact data and must be content-free."""
    runner = _runner_module()

    unsafe_reason_codes = (
        "https://git.linecorp.com/org/repo/pull/1",
        "token=ghp_secret123456789",
        "diff --git a/private.py b/private.py",
        "missing workspace: /Users/alice/private/repo",
    )

    for reason_code in unsafe_reason_codes:
        with pytest.raises(ValueError, match="unavailable reason code"):
            runner.EvaluationCaseUnavailable(reason_code)


def test_runner_invalid_suite_schema_exits_non_zero(
    tmp_path: Path,
) -> None:
    """Invalid suite manifests should fail configuration fast with exit code 2."""
    runner = _runner_module()
    manifest_path = tmp_path / "cases.yaml"
    manifest_path.write_text(
        "cases:\n"
        "  - case_id: broken\n"
        "    source_format: synthetic_replay\n",
    )

    def unused_scan_case(case: EvaluationCase) -> Report:
        raise AssertionError(f"scan_case should not be called: {case.case_id}")

    with pytest.raises(SystemExit) as exit_info:
        runner.run_evaluation_suite_or_exit(
            manifest_path,
            scan_case=unused_scan_case,
        )

    assert exit_info.value.code == 2


def test_runner_unexpected_runtime_errors_still_crash_suite() -> None:
    """Only known case-level unavailability should degrade gracefully."""
    runner = _runner_module()

    def scan_case(case: EvaluationCase) -> Report:
        raise RuntimeError(f"boom: {case.case_id}")

    with pytest.raises(RuntimeError, match="boom: case-source-present"):
        runner.run_evaluation_cases(cases=(_case(),), scan_case=scan_case)


def test_runner_scan_case_signature_is_source_present_or_replay_friendly() -> None:
    """Runner should delegate acquisition details to the injected scan callable."""
    runner = _runner_module()
    seen_cases: list[str] = []

    def scan_case(case: EvaluationCase) -> Report:
        seen_cases.append(case.case_id)
        return _report()

    scan_callable: Callable[[EvaluationCase], Report] = scan_case
    runner.run_evaluation_cases(
        cases=(_case(case_id="case-a"), _case(case_id="case-b")),
        scan_case=scan_callable,
    )

    assert seen_cases == ["case-a", "case-b"]
