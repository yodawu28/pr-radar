import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pr_radar.contracts.base import StrictContract
from pr_radar.evaluation.contracts import RunManifest, _reject_raw_metadata_text
from pr_radar.evaluation.runner import EvaluationRunResult


_SUMMARY_ARTIFACT = "eval-summary.md"
_RESULTS_ARTIFACT = "eval-results.json"
_MANIFEST_ARTIFACT = "run-manifest.json"


class EvaluationArtifactsWritten(StrictContract):
    artifact_paths: tuple[Path, ...]


def write_evaluation_artifacts(
    *,
    output_dir: Path,
    result: EvaluationRunResult,
    run_manifest: RunManifest,
) -> EvaluationArtifactsWritten:
    """Write Sprint 5 content-free evaluation artifacts."""
    result_payload = result.model_dump(mode="json")
    manifest_payload = run_manifest.model_dump(mode="json")
    summary_text = _render_summary(result)

    _assert_content_free(result_payload)
    _assert_content_free(manifest_payload)
    _assert_content_free(summary_text)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / _SUMMARY_ARTIFACT
    results_path = output_dir / _RESULTS_ARTIFACT
    manifest_path = output_dir / _MANIFEST_ARTIFACT

    summary_path.write_text(summary_text)
    results_path.write_text(_json_dumps(result_payload))
    manifest_path.write_text(_json_dumps(manifest_payload))

    return EvaluationArtifactsWritten(
        artifact_paths=(summary_path, results_path, manifest_path),
    )


def _render_summary(result: EvaluationRunResult) -> str:
    overall = result.metrics.overall
    return "\n".join(
        (
            "# PR Radar Evaluation Summary",
            "",
            f"Cases: {overall.case_count}",
            f"Evaluated: {overall.evaluated_case_count}",
            f"Unavailable: {overall.unavailable_case_count}",
            f"Invalid: {overall.invalid_case_count}",
            f"Precision: {overall.precision:.3f}",
            f"Recall: {overall.recall:.3f}",
            (
                "Recommendation Agreement: "
                f"{overall.recommendation_agreement_rate:.3f}"
            ),
            f"Coverage Gaps: {overall.coverage_gap_count}",
            "",
        ),
    )


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _assert_content_free(value: object) -> None:
    try:
        _walk_content(value)
    except ValueError as error:
        raise ValueError("evaluation artifact payload must be content-free") from error


def _walk_content(value: object) -> None:
    if isinstance(value, str):
        _reject_raw_metadata_text(value)
        return
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            _walk_content(key)
            _walk_content(nested_value)
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        for nested_value in value:
            _walk_content(nested_value)
