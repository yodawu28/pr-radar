from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Never

import typer

from pr_radar.evaluation import (
    EvaluationCase,
    EvaluationCaseUnavailable,
    RunManifest,
    run_evaluation_suite_or_exit,
    write_evaluation_artifacts,
)

_EVAL_SUMMARY_ARTIFACT = "eval-summary.md"
_EVAL_RESULTS_ARTIFACT = "eval-results.json"
_EVAL_MANIFEST_ARTIFACT = "run-manifest.json"


def eval_suite(
    manifest_path: Path,
    output_dir: Path = typer.Option(
        Path("evaluation/outputs"),
        "--output-dir",
        help="Write content-free evaluation artifacts to this directory.",
    ),
) -> None:
    """Run an evaluation manifest and write content-free artifacts."""
    started_at = _utc_timestamp()
    try:
        result = run_evaluation_suite_or_exit(
            manifest_path,
            scan_case=_unavailable_eval_scan_case,
        )
    except SystemExit as error:
        raise typer.Exit(code=_exit_code(error)) from error

    completed_at = _utc_timestamp()
    run_manifest = _build_eval_run_manifest(
        manifest_path=manifest_path,
        output_dir=output_dir,
        started_at=started_at,
        completed_at=completed_at,
        case_count=result.metrics.overall.case_count,
    )
    written = write_evaluation_artifacts(
        output_dir=output_dir,
        result=result,
        run_manifest=run_manifest,
    )

    for artifact_path in written.artifact_paths:
        typer.echo(artifact_path)


def _unavailable_eval_scan_case(_case: EvaluationCase) -> Never:
    raise EvaluationCaseUnavailable("scan_adapter_unavailable")


def _build_eval_run_manifest(
    *,
    manifest_path: Path,
    output_dir: Path,
    started_at: str,
    completed_at: str,
    case_count: int,
) -> RunManifest:
    return RunManifest(
        run_id=f"eval-{started_at.replace(':', '').replace('-', '')}",
        tool_version=_tool_version(),
        started_at=started_at,
        completed_at=completed_at,
        case_count=case_count,
        input_hashes={manifest_path.name: f"sha256:{_file_sha256(manifest_path)}"},
        artifact_paths=(
            _EVAL_SUMMARY_ARTIFACT,
            _EVAL_RESULTS_ARTIFACT,
            _EVAL_MANIFEST_ARTIFACT,
        ),
    )


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _tool_version() -> str:
    try:
        return version("pr-radar")
    except PackageNotFoundError:
        return "0.1.0"


def _exit_code(error: SystemExit) -> int:
    code = error.code
    if isinstance(code, int):
        return code
    return 1
