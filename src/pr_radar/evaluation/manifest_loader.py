from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pr_radar.adapters.local_files.structured_records import load_structured_records
from pr_radar.evaluation.contracts import EvaluationCase
from pr_radar.evaluation.contracts import _reject_raw_metadata_text

_CONTENT_FREE_ERROR = "evaluation manifest must be content-free"


class EvaluationManifestLoadError(ValueError):
    pass


def load_evaluation_manifest(path: Path | str) -> tuple[EvaluationCase, ...]:
    manifest_path = Path(path)
    try:
        raw_cases = load_structured_records(manifest_path, root_key="cases")
        return tuple(
            EvaluationCase.model_validate(_content_free_payload(raw_case))
            for raw_case in raw_cases
        )
    except (OSError, ValueError, TypeError, ValidationError) as error:
        raise EvaluationManifestLoadError(
            _manifest_load_error_message(manifest_path, error),
        ) from error


def load_evaluation_manifest_or_exit(path: Path | str) -> tuple[EvaluationCase, ...]:
    try:
        return load_evaluation_manifest(path)
    except EvaluationManifestLoadError as error:
        raise SystemExit(2) from error


def _manifest_load_error_message(path: Path, error: Exception) -> str:
    if path.suffix.lower() in {".yaml", ".yml"} and "YAML" in str(error):
        return "invalid YAML manifest"
    return str(error)


def _content_free_payload(value: Any) -> Any:
    if isinstance(value, str):
        _reject_manifest_text(value)
        return value
    if isinstance(value, Mapping):
        return {
            _content_free_mapping_key(key): _content_free_payload(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_content_free_payload(nested_value) for nested_value in value]
    return value


def _content_free_mapping_key(key: Any) -> Any:
    if isinstance(key, str):
        _reject_manifest_text(key)
    return key


def _reject_manifest_text(value: str) -> None:
    try:
        _reject_raw_metadata_text(value)
    except ValueError as error:
        raise ValueError(_CONTENT_FREE_ERROR) from error
