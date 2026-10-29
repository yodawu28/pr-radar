from importlib import import_module

import pytest
from pydantic import ValidationError


def _evaluation_contracts():
    try:
        module = import_module("pr_radar.evaluation.contracts")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.contracts: {error}")

    missing = tuple(
        name
        for name in (
            "EvaluationCase",
            "EvaluationCaseStatus",
            "ExpectedFinding",
            "ExpectedSeverity",
            "FindingMatchResult",
            "MatchOutcome",
            "MetricsSummary",
            "CaseEvaluationResult",
            "RunManifest",
        )
        if not hasattr(module, name)
    )

    assert missing == (), (
        "expected Sprint 5 evaluation contract names exported by "
        f"pr_radar.evaluation.contracts: {missing}"
    )
    return module


def test_ground_truth_case_contract_keeps_aimigo_metadata_content_free() -> None:
    """Catches storing raw Aimigo patch/source instead of normalized metadata."""
    contracts = _evaluation_contracts()

    expected = contracts.ExpectedFinding(
        finding_id="expected:java.spring.biz.immutable_amount",
        pillar="security_supply_chain",
        reason_code="immutable_amount_violation",
        evidence_path="src/main/java/com/acme/orders/OrderService.java",
        severity="high_risk",
        source_rule_id="java.spring.biz.immutable_amount",
        source_line=16,
        source_excerpt_hash="sha256:expected-evidence",
        labels=("aimigo", "java-spring"),
    )
    case = contracts.EvaluationCase(
        case_id="case-01-biz-immutable-amount",
        source_format="aimigo_bench_case",
        pr_id="case-01-biz-immutable-amount",
        stack="java-spring",
        ruleset_version="0.1.0",
        labels=("business-rule",),
        source_refs=(
            "ground_truth.json:sha256:metadata",
            "patch.diff:sha256:local-input",
        ),
        expected_findings=(expected,),
    )

    assert case.expected_findings == (expected,)
    assert case.source_refs == (
        "ground_truth.json:sha256:metadata",
        "patch.diff:sha256:local-input",
    )
    assert expected.severity == "high_risk"
    assert expected.source_rule_id == "java.spring.biz.immutable_amount"


def test_ground_truth_case_contract_records_partial_unavailable_fields() -> None:
    """Catches guessing missing optional Aimigo fields during data repair."""
    contracts = _evaluation_contracts()

    expected = contracts.ExpectedFinding(
        finding_id="expected:partial:case-78",
        pillar="test_integrity",
        reason_code="unmapped_external_rule",
        evidence_path="tests/test_checkout.py",
        severity="warning",
        partial_fields=("ruleId", "title", "evidence"),
        unavailable_fields=("source_rule_id",),
    )
    case = contracts.EvaluationCase(
        case_id="case-78-challenge-5-files",
        source_format="aimigo_bench_case",
        pr_id="case-78-challenge-5-files",
        stack=None,
        ruleset_version=None,
        labels=(),
        source_refs=("ground_truth.json:sha256:partial-metadata",),
        expected_findings=(expected,),
        partial_fields=("stack", "ruleset_version"),
    )

    assert expected.partial_fields == ("ruleId", "title", "evidence")
    assert expected.unavailable_fields == ("source_rule_id",)
    assert case.partial_fields == ("stack", "ruleset_version")


def test_evaluation_status_match_and_metrics_contracts_are_deterministic() -> None:
    """Catches prose-only evaluation output without measurable outcomes."""
    contracts = _evaluation_contracts()

    assert contracts.EvaluationCaseStatus.__args__ == (
        "evaluated",
        "unavailable",
        "invalid",
    )
    assert contracts.MatchOutcome.__args__ == (
        "matched_expected",
        "missing_expected",
        "unexpected_actual",
        "low_confidence_match",
    )

    match = contracts.FindingMatchResult(
        outcome="matched_expected",
        expected_finding_id="expected:dependency.added.requests",
        actual_finding_id="dependency.added.requests",
        pillar="security_supply_chain",
        reason_code="unapproved_dependency_added",
        evidence_path="pyproject.toml",
        match_reason_code="pillar_reason_path_match",
    )
    case_result = contracts.CaseEvaluationResult(
        case_id="case-001",
        status="evaluated",
        match_results=(match,),
        expected_recommendation="APPROVE_WITH_CAUTION",
        actual_recommendation="APPROVE_WITH_CAUTION",
        recommendation_agreement=True,
    )
    metrics = contracts.MetricsSummary(
        case_count=1,
        evaluated_case_count=1,
        unavailable_case_count=0,
        invalid_case_count=0,
        expected_finding_count=1,
        true_positive_count=1,
        false_positive_count=0,
        false_negative_count=0,
        low_confidence_match_count=0,
        coverage_gap_count=0,
        precision=1.0,
        recall=1.0,
        recommendation_agreement_rate=1.0,
    )

    assert case_result.match_results == (match,)
    assert case_result.recommendation_agreement is True
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0


def test_run_manifest_contract_records_content_free_artifact_metadata() -> None:
    """Catches evaluation artifacts that cannot be audited without raw content."""
    contracts = _evaluation_contracts()

    manifest = contracts.RunManifest(
        run_id="eval-20261028-000001",
        tool_version="0.1.0",
        started_at="2026-10-28T00:00:00Z",
        completed_at="2026-10-28T00:00:01Z",
        case_count=2,
        ruleset_versions=("0.1.0", "0.2.0"),
        input_hashes={
            "case-001/ground_truth.json": "sha256:metadata",
            "case-001/patch.diff": "sha256:local-input",
        },
        artifact_paths=(
            "evaluation/outputs/eval-summary.md",
            "evaluation/outputs/eval-results.json",
            "evaluation/outputs/run-manifest.json",
        ),
    )

    assert manifest.case_count == 2
    assert manifest.ruleset_versions == ("0.1.0", "0.2.0")
    assert "case-001/patch.diff" in manifest.input_hashes


def test_evaluation_contracts_reject_raw_diff_source_and_unredacted_content() -> None:
    """Locks the Sprint 5 content-free artifact boundary into the schema."""
    contracts = _evaluation_contracts()

    with pytest.raises(ValidationError):
        contracts.ExpectedFinding(
            finding_id="expected:raw",
            pillar="security_supply_chain",
            reason_code="raw_content_leak",
            evidence_path="src/service.py",
            severity="high_risk",
            evidence="line 1: password = 'secret'",
        )

    with pytest.raises(ValidationError):
        contracts.EvaluationCase(
            case_id="case-raw",
            source_format="aimigo_bench_case",
            pr_id="case-raw",
            source_refs=("patch.diff:sha256:local-input",),
            expected_findings=(),
            raw_patch="diff --git a/src/service.py b/src/service.py",
        )

    with pytest.raises(ValidationError):
        contracts.RunManifest(
            run_id="eval-raw",
            tool_version="0.1.0",
            started_at="2026-10-28T00:00:00Z",
            case_count=1,
            input_hashes={},
            raw_source="class Secret: pass",
        )


def test_evaluation_contracts_reject_raw_content_in_allowed_metadata_fields() -> None:
    """Prevents raw evidence from being smuggled through hash/ref metadata."""
    contracts = _evaluation_contracts()

    with pytest.raises(ValidationError):
        contracts.ExpectedFinding(
            finding_id="expected:raw-excerpt",
            pillar="security_supply_chain",
            reason_code="raw_content_leak",
            evidence_path="src/service.py",
            severity="high_risk",
            source_excerpt_hash="password=secret-token",
        )

    with pytest.raises(ValidationError):
        contracts.EvaluationCase(
            case_id="case-raw-source-ref",
            source_format="aimigo_bench_case",
            pr_id="case-raw-source-ref",
            source_refs=("diff --git a/src/service.py b/src/service.py",),
            expected_findings=(),
        )

    with pytest.raises(ValidationError):
        contracts.RunManifest(
            run_id="eval-raw-input-hash",
            tool_version="0.1.0",
            started_at="2026-10-28T00:00:00Z",
            case_count=1,
            input_hashes={
                "case-001/patch.diff": "diff --git a/x b/x\n+password=secret",
            },
        )
