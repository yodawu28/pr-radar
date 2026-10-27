from collections.abc import Mapping
from importlib import import_module, util
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from pr_radar.contracts import PrEvidencePack, PrInput, PrMetadata, RawEvidence
from pr_radar.scan import scan_pr


PROJECT_ROOT = Path(__file__).parents[1]


def _module(module_name: str):
    assert util.find_spec(module_name) is not None, (
        f"expected {module_name} to provide the ADR-021 boundary"
    )
    return import_module(module_name)


def _empty_evidence_pack(pr_input: PrInput) -> PrEvidencePack:
    return PrEvidencePack(
        pr_input=pr_input,
        pr_metadata=PrMetadata(
            title="No risky changes",
            body="",
            author_login="alice",
            head_ref="feature/no-risk",
            base_ref="main",
        ),
        raw_evidence=RawEvidence(diff=""),
    )


def test_scan_policy_defaults_are_internal_and_drive_fetch_options(
    monkeypatch,
) -> None:
    """Keeps budget/file-content policy out of ad hoc scan.py literals."""
    scan_policy = _module("pr_radar.application.scan_policy")
    captured_include_file_contents: list[bool] = []

    def fake_fetch_pr_evidence(
        pr_input: PrInput,
        *,
        env: Mapping[str, str],
        http_get,
        include_file_contents: bool = False,
    ) -> PrEvidencePack:
        captured_include_file_contents.append(include_file_contents)
        return _empty_evidence_pack(pr_input)

    monkeypatch.setattr(
        "pr_radar.application.scan.fetch_pr_evidence",
        fake_fetch_pr_evidence,
    )

    assert scan_policy.DEFAULT_SCAN_POLICY.static_context_max_chars == 12_000
    assert scan_policy.DEFAULT_SCAN_POLICY.blast_radius_max_dependents == 25
    assert scan_policy.DEFAULT_SCAN_POLICY.include_file_contents is True

    custom_policy = scan_policy.ScanPolicy(
        static_context_max_chars=777,
        blast_radius_max_dependents=3,
        include_file_contents=False,
    )
    report = scan_pr(
        "https://github.com/example/repo/pull/17",
        fetch_evidence=True,
        scan_policy=custom_policy,
        env={"GITHUB_TOKEN": "github_unit_secret_value"},
        http_get=lambda url, *, headers: None,
    )

    assert captured_include_file_contents == [False]
    assert report.evaluation_metadata["context_budget_max_chars"] == "777"


def test_scan_evaluation_metadata_is_typed_before_report_projection() -> None:
    """Prevents typo-prone dict assembly from becoming the scan boundary."""
    scan_metadata = _module("pr_radar.application.scan_metadata")
    metadata_keys = _module("pr_radar.contracts.metadata_keys")

    metadata = scan_metadata.ScanEvaluationMetadata(
        context_grade="review_grade",
        context_envelope="available",
        context_finding_count=2,
        context_budget_max_chars=777,
        context_budget_used_chars=321,
        context_budget_is_over_budget=False,
        blast_radius_context_grade="unavailable",
        blast_radius_availability="unavailable",
        blast_radius_reason_code="requires_local_workspace",
        blast_radius_dependent_count=0,
        blast_radius_truncated=False,
        blast_radius_changed_paths=("src/service.py",),
        blast_radius_direct_dependents=(),
    )

    projected = metadata.to_report_metadata()

    assert projected[metadata_keys.CONTEXT_GRADE] == "review_grade"
    assert projected[metadata_keys.CONTEXT_BUDGET_MAX_CHARS] == "777"
    assert projected[metadata_keys.CONTEXT_BUDGET_IS_OVER_BUDGET] == "False"
    assert projected[metadata_keys.BLAST_RADIUS_CHANGED_PATHS] == "src/service.py"
    assert all(isinstance(key, str) for key in projected)
    assert all(isinstance(value, str) for value in projected.values())

    with pytest.raises(ValidationError):
        scan_metadata.ScanEvaluationMetadata(
            context_grade="review_grade",
            context_envelope="available",
            context_finding_count=0,
            context_budget_max_chars=777,
            context_budget_used_chars=0,
            context_budget_is_over_budget=False,
            blast_radius_context_grade="unavailable",
            blast_radius_availability="unavailable",
            blast_radius_reason_code="requires_local_workspace",
            blast_radius_dependent_count=0,
            blast_radius_truncated=False,
            unexpected_metadata_key="typo",
        )


def test_scan_blast_radius_context_grade_uses_metadata_literal_type() -> None:
    """Catches assignment drift from plain str into typed scan metadata."""
    scan = _module("pr_radar.application.scan")
    scan_metadata = _module("pr_radar.application.scan_metadata")

    type_hints = get_type_hints(scan._blast_radius_context_grade)

    assert type_hints["return"] == scan_metadata.ContextGrade


def test_scan_metadata_keys_are_contract_constants_not_scan_literals() -> None:
    """Makes report/CLI metadata keys a shared contract vocabulary."""
    metadata_keys = _module("pr_radar.contracts.metadata_keys")
    scan_source = (PROJECT_ROOT / "src/pr_radar/application/scan.py").read_text()

    expected_keys = {
        "context_grade": metadata_keys.CONTEXT_GRADE,
        "context_envelope": metadata_keys.CONTEXT_ENVELOPE,
        "context_budget_max_chars": metadata_keys.CONTEXT_BUDGET_MAX_CHARS,
        "blast_radius_context_grade": metadata_keys.BLAST_RADIUS_CONTEXT_GRADE,
        "blast_radius_availability": metadata_keys.BLAST_RADIUS_AVAILABILITY,
        "blast_radius_reason_code": metadata_keys.BLAST_RADIUS_REASON_CODE,
        "blast_radius_direct_dependents": (
            metadata_keys.BLAST_RADIUS_DIRECT_DEPENDENTS
        ),
    }

    assert expected_keys == {key: key for key in expected_keys}
    for key in expected_keys:
        assert f'"{key}"' not in scan_source


def test_low_confidence_tag_is_shared_canonical_vocabulary() -> None:
    """Prevents detector families and scan filtering from drifting."""
    findings = _module("pr_radar.contracts.findings")
    assert findings.LOW_CONFIDENCE_TAG == "low_confidence"

    source_paths = (
        "src/pr_radar/application/scan.py",
        "src/pr_radar/detectors/deployment_downtime/migrations.py",
        "src/pr_radar/detectors/test_integrity/test_shape.py",
    )
    for relative_path in source_paths:
        source = (PROJECT_ROOT / relative_path).read_text()
        assert '"low confidence"' not in source
        assert "'low confidence'" not in source
