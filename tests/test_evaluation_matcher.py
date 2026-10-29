from collections.abc import Mapping
from importlib import import_module

import pytest

from pr_radar.contracts import Finding, LOW_CONFIDENCE_TAG, RadarPillarKey
from pr_radar.evaluation.contracts import ExpectedFinding


def _matcher_module():
    try:
        return import_module("pr_radar.evaluation.matcher")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.matcher: {error}")


def _expected(
    *,
    finding_id: str = "expected:migration.destructive.schema_change",
    pillar: RadarPillarKey = "deployment_downtime",
    reason_code: str = "destructive_migration_data_loss_risk",
    evidence_path: str = "db/migrate/001_drop_column.sql",
    source_rule_id: str | None = None,
) -> ExpectedFinding:
    return ExpectedFinding(
        finding_id=finding_id,
        pillar=pillar,
        reason_code=reason_code,
        evidence_path=evidence_path,
        severity="high_risk",
        source_rule_id=source_rule_id,
    )


def _actual(
    *,
    finding_id: str = "migration.destructive.schema_change",
    pillar: RadarPillarKey = "deployment_downtime",
    reason_code: str = "destructive_migration_data_loss_risk",
    evidence_path: str = "db/migrate/001_drop_column.sql",
    confidence: float = 0.86,
    score: int = 88,
    tags: tuple[str, ...] = (),
) -> Finding:
    return Finding(
        id=finding_id,
        pillar=pillar,
        title="Destructive migration requires deployment review",
        status="high",
        score=score,
        confidence=confidence,
        evidence_refs=(f"file:{evidence_path}", f"diff:{evidence_path}"),
        decision_source="deterministic",
        calibration_reason=reason_code,
        tags=tags,
    )


def test_matches_expected_findings_by_pillar_reason_and_evidence_path() -> None:
    """Locks primary matching without depending on prose or title similarity."""
    matcher = _matcher_module()

    results = matcher.match_findings(
        expected_findings=(
            _expected(),
            _expected(
                finding_id="expected:dependency.added.pyproject",
                pillar="security_supply_chain",
                reason_code="dependency_added_manifest_requires_supply_chain_review",
                evidence_path="pyproject.toml",
            ),
        ),
        actual_findings=(
            _actual(
                finding_id="dependency.added.pyproject",
                pillar="security_supply_chain",
                reason_code="dependency_added_manifest_requires_supply_chain_review",
                evidence_path="pyproject.toml",
                score=68,
                confidence=0.74,
            ),
            _actual(),
        ),
    )

    assert [(result.outcome, result.expected_finding_id) for result in results] == [
        ("matched_expected", "expected:dependency.added.pyproject"),
        ("matched_expected", "expected:migration.destructive.schema_change"),
    ]
    assert {result.match_reason_code for result in results} == {
        "pillar_reason_path_match",
    }


def test_matches_external_rule_id_through_explicit_mapping() -> None:
    """Locks secondary matching for Aimigo ruleId without guessing from prose."""
    matcher = _matcher_module()
    rule_id_mapping: Mapping[str, tuple[str, str]] = {
        "java.spring.biz.immutable_amount": (
            "security_supply_chain",
            "immutable_amount_violation",
        ),
    }

    results = matcher.match_findings(
        expected_findings=(
            _expected(
                finding_id="expected:java.spring.biz.immutable_amount",
                pillar="test_integrity",
                reason_code="unmapped_external_rule",
                evidence_path="src/main/java/com/acme/orders/OrderService.java",
                source_rule_id="java.spring.biz.immutable_amount",
            ),
        ),
        actual_findings=(
            _actual(
                finding_id="business_rule.immutable_amount",
                pillar="security_supply_chain",
                reason_code="immutable_amount_violation",
                evidence_path="src/main/java/com/acme/orders/OrderService.java",
            ),
        ),
        rule_id_mapping=rule_id_mapping,
    )

    assert len(results) == 1
    assert results[0].outcome == "matched_expected"
    assert results[0].expected_finding_id == "expected:java.spring.biz.immutable_amount"
    assert results[0].actual_finding_id == "business_rule.immutable_amount"
    assert results[0].match_reason_code == "external_rule_id_mapping"


def test_external_rule_mapping_rejects_unknown_radar_pillar() -> None:
    """Prevents invalid mapping config from producing optimistic matches."""
    matcher = _matcher_module()
    rule_id_mapping: Mapping[str, tuple[str, str]] = {
        "external.invalid": (
            "unknown_future_pillar",
            "immutable_amount_violation",
        ),
    }

    with pytest.raises(ValueError, match="unknown radar pillar"):
        matcher.match_findings(
            expected_findings=(
                _expected(
                    finding_id="expected:external.invalid",
                    pillar="test_integrity",
                    reason_code="unmapped_external_rule",
                    evidence_path="src/main/java/com/acme/orders/OrderService.java",
                    source_rule_id="external.invalid",
                ),
            ),
            actual_findings=(
                _actual(
                    finding_id="business_rule.immutable_amount",
                    pillar="security_supply_chain",
                    reason_code="immutable_amount_violation",
                    evidence_path="src/main/java/com/acme/orders/OrderService.java",
                ),
            ),
            rule_id_mapping=rule_id_mapping,
        )


def test_reports_missing_expected_and_unexpected_actual_findings() -> None:
    """Locks recall and false-positive inputs for Sprint 5 metrics."""
    matcher = _matcher_module()

    results = matcher.match_findings(
        expected_findings=(
            _expected(finding_id="expected:missing"),
        ),
        actual_findings=(
            _actual(
                finding_id="dependency.added.package_json",
                pillar="security_supply_chain",
                reason_code="dependency_added_manifest_requires_supply_chain_review",
                evidence_path="package.json",
            ),
        ),
    )

    assert [(result.outcome, result.match_reason_code) for result in results] == [
        ("missing_expected", "no_actual_match"),
        ("unexpected_actual", "no_expected_match"),
    ]
    assert results[0].expected_finding_id == "expected:missing"
    assert results[1].actual_finding_id == "dependency.added.package_json"


def test_duplicate_actual_matches_are_deterministic_and_reported() -> None:
    """Prevents duplicate detector output from inflating true positives."""
    matcher = _matcher_module()

    results = matcher.match_findings(
        expected_findings=(
            _expected(),
        ),
        actual_findings=(
            _actual(
                finding_id="migration.destructive.schema_change.low_confidence",
                confidence=0.70,
                score=86,
            ),
            _actual(
                finding_id="migration.destructive.schema_change",
                confidence=0.92,
                score=90,
            ),
        ),
    )

    assert [(result.outcome, result.actual_finding_id) for result in results] == [
        ("matched_expected", "migration.destructive.schema_change"),
        ("unexpected_actual", "migration.destructive.schema_change.low_confidence"),
    ]
    assert results[1].match_reason_code == "duplicate_actual_match"


def test_single_actual_match_cannot_satisfy_multiple_expected_findings() -> None:
    """Prevents one detector hit from inflating recall across duplicate labels."""
    matcher = _matcher_module()

    results = matcher.match_findings(
        expected_findings=(
            _expected(finding_id="expected:one"),
            _expected(finding_id="expected:two"),
        ),
        actual_findings=(
            _actual(),
        ),
    )

    assert [
        (result.outcome, result.expected_finding_id, result.actual_finding_id)
        for result in results
    ] == [
        (
            "matched_expected",
            "expected:one",
            "migration.destructive.schema_change",
        ),
        ("missing_expected", "expected:two", None),
    ]


def test_low_confidence_matches_are_separated_from_primary_matches() -> None:
    """Keeps low-confidence findings visible without counting as primary TP."""
    matcher = _matcher_module()

    results = matcher.match_findings(
        expected_findings=(
            _expected(
                finding_id="expected:test_shape.missing_behavior_coverage",
                pillar="test_integrity",
                reason_code="behavior_change_without_test_evidence_low_confidence",
                evidence_path="src/orders/service.py",
            ),
        ),
        actual_findings=(
            _actual(
                finding_id="test_shape.missing_behavior_coverage",
                pillar="test_integrity",
                reason_code="behavior_change_without_test_evidence_low_confidence",
                evidence_path="src/orders/service.py",
                confidence=0.52,
                score=58,
                tags=(LOW_CONFIDENCE_TAG,),
            ),
        ),
    )

    assert len(results) == 1
    assert results[0].outcome == "low_confidence_match"
    assert results[0].match_reason_code == "low_confidence_match"
