import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from yaml import YAMLError
from yaml import safe_load


def load_structured_records(
    path: Path | str,
    *,
    root_key: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    record_path = Path(path)
    suffix = record_path.suffix.lower()
    text = record_path.read_text()
    if suffix == ".jsonl":
        return _load_jsonl_records(text)
    if suffix == ".json":
        return _load_json_records(text, root_key=root_key)
    if suffix in {".yaml", ".yml"}:
        return _load_yaml_records(text, root_key=root_key)
    raise ValueError(f"unsupported structured record format: {suffix}")


def _load_jsonl_records(text: str) -> tuple[Mapping[str, Any], ...]:
    records = tuple(
        json.loads(line)
        for line in text.splitlines()
        if line.strip()
    )
    return _ensure_mapping_records(records)


def _load_json_records(
    text: str,
    *,
    root_key: str | None,
) -> tuple[Mapping[str, Any], ...]:
    payload = json.loads(text)
    return _records_from_payload(
        payload,
        root_key=root_key,
        missing_root_message="structured record root key is missing",
    )


def _records_from_payload(
    payload: Any,
    *,
    root_key: str | None,
    missing_root_message: str,
) -> tuple[Mapping[str, Any], ...]:
    if root_key is not None:
        if not isinstance(payload, Mapping) or root_key not in payload:
            raise ValueError(missing_root_message)
        return _ensure_mapping_records(payload[root_key])
    if isinstance(payload, list):
        return _ensure_mapping_records(payload)
    return _ensure_mapping_records((payload,))


def _load_yaml_records(
    text: str,
    *,
    root_key: str | None,
) -> tuple[Mapping[str, Any], ...]:
    try:
        payload = safe_load(text)
    except YAMLError as error:
        raise ValueError("invalid YAML structured records") from error
    return _records_from_payload(
        payload,
        root_key=root_key,
        missing_root_message="YAML structured record root key is missing",
    )


def _ensure_mapping_records(records: Iterable[Any]) -> tuple[Mapping[str, Any], ...]:
    mapped_records = tuple(records)
    if not all(isinstance(record, Mapping) for record in mapped_records):
        raise ValueError("structured records must be mappings")
    return mapped_records  # type: ignore[return-value]
