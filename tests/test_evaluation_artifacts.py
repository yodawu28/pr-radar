import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from pr_radar.evaluation.contracts import (
    CaseEvaluationResult,
    FindingMatchResult,
    RunManifest,
)
from pr_radar.evaluation.metrics import summarize_metrics
from pr_radar.evaluation.runner import EvaluationRunResult


def _artifacts_module() -> Any:
    try:
        module = import_module("pr_radar.evaluation.artifacts")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.artifacts: {error}")

    assert hasattr(module, "write_evaluation_artifacts"), (
        "expected pr_radar.evaluation.artifacts.write_evaluation_artifacts"
    )
    return module


def _matched_case(case_id: str = "case-001") -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case_id,
        status="evaluated",
        match_results=(
            FindingMatchResult(
                outcome="matched_expected",
                expected_finding_id="expected:dependency.added.pyproject",
                actual_finding_id="dependency.added.pyproject",
                pillar="security_supply_chain",
                reason_code="dependency_added_manifest_requires_supply_chain_review",
                evidence_path="pyproject.toml",
                match_reason_code="pillar_reason_path_match",
            ),
        ),
        expected_recommendation="REQUEST_CHANGES",
        actual_recommendation="REQUEST_CHANGES",
        recommendation_agreement=True,
    )


def _run_result(
    *,
    case_results: tuple[CaseEvaluationResult, ...] | None = None,
) -> EvaluationRunResult:
    results = case_results or (_matched_case(),)
    return EvaluationRunResult(
        case_results=results,
        metrics=summarize_metrics(case_results=results),
    )


def _run_manifest() -> RunManifest:
    return RunManifest(
        run_id="eval-20261029-000001",
        tool_version="0.1.0",
        started_at="2026-10-29T00:00:00Z",
        completed_at="2026-10-29T00:00:01Z",
        case_count=1,
        ruleset_versions=("synthetic-v1",),
        input_hashes={"evaluation/bench/cases/public/case-001.yaml": "sha256:abc123"},
        artifact_paths=(
            "evaluation/outputs/eval-summary.md",
            "evaluation/outputs/eval-results.json",
            "evaluation/outputs/run-manifest.json",
        ),
    )


def test_writes_evaluation_artifact_trio_content_free(tmp_path: Path) -> None:
    """Locks Sprint 5 artifact names and content-free baseline output."""
    artifacts = _artifacts_module()
    output_dir = tmp_path / "evaluation" / "outputs"

    written = artifacts.write_evaluation_artifacts(
        output_dir=output_dir,
        result=_run_result(),
        run_manifest=_run_manifest(),
    )

    expected_paths = {
        output_dir / "eval-summary.md",
        output_dir / "eval-results.json",
        output_dir / "run-manifest.json",
    }
    assert set(written.artifact_paths) == expected_paths
    for artifact_path in expected_paths:
        assert artifact_path.exists()

    summary_text = (output_dir / "eval-summary.md").read_text()
    results_payload = json.loads((output_dir / "eval-results.json").read_text())
    manifest_payload = json.loads((output_dir / "run-manifest.json").read_text())

    assert "Precision: 1.000" in summary_text
    assert results_payload["metrics"]["overall"]["true_positive_count"] == 1
    assert results_payload["case_results"][0]["case_id"] == "case-001"
    assert manifest_payload["run_id"] == "eval-20261029-000001"

    combined_artifacts = "\n".join(
        artifact_path.read_text() for artifact_path in sorted(expected_paths)
    )
    forbidden_fragments = (
        "diff --git",
        "PRIVATE_RAW_SOURCE",
        "api_key=sk_live_1234567890",
        "https://git.linecorp.com",
    )
    for forbidden_fragment in forbidden_fragments:
        assert forbidden_fragment not in combined_artifacts


def test_rejects_raw_content_in_artifact_payload_before_write(tmp_path: Path) -> None:
    """Artifact writer must fail closed if an upstream result carries raw text."""
    artifacts = _artifacts_module()
    output_dir = tmp_path / "evaluation" / "outputs"
    unsafe_result = _run_result(
        case_results=(
            _matched_case(case_id="diff --git a/private.py b/private.py"),
        ),
    )

    with pytest.raises(ValueError, match="content-free"):
        artifacts.write_evaluation_artifacts(
            output_dir=output_dir,
            result=unsafe_result,
            run_manifest=_run_manifest(),
        )

    assert not (output_dir / "eval-summary.md").exists()
    assert not (output_dir / "eval-results.json").exists()
    assert not (output_dir / "run-manifest.json").exists()


def test_generated_evaluation_outputs_are_gitignored() -> None:
    """Generated benchmark artifacts must stay out of tracked source by default."""
    gitignore = Path(".gitignore").read_text()

    assert "evaluation/outputs/" in gitignore
