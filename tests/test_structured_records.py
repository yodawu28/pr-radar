import json
from importlib import import_module
from pathlib import Path

import pytest


def _records_module():
    try:
        return import_module("pr_radar.adapters.local_files.structured_records")
    except ModuleNotFoundError as error:
        pytest.fail(
            "expected importable pr_radar.adapters.local_files.structured_records: "
            f"{error}"
        )


def test_loads_jsonl_structured_records(tmp_path: Path) -> None:
    """Locks reusable local JSONL record parsing outside evaluation domain."""
    records = _records_module()
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps({"case_id": "case-1", "source_refs": []})
        + "\n"
        + json.dumps({"case_id": "case-2", "source_refs": []})
        + "\n",
    )

    loaded = records.load_structured_records(path)

    assert loaded == (
        {"case_id": "case-1", "source_refs": []},
        {"case_id": "case-2", "source_refs": []},
    )


def test_loads_json_root_key_structured_records(tmp_path: Path) -> None:
    """Locks the root-key adapter contract needed by evaluation manifests."""
    records = _records_module()
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"case_id": "case-1"},
                    {"case_id": "case-2"},
                ],
            },
        ),
    )

    loaded = records.load_structured_records(path, root_key="cases")

    assert loaded == ({"case_id": "case-1"}, {"case_id": "case-2"})


def test_loads_minimal_yaml_root_key_structured_records(tmp_path: Path) -> None:
    """Locks the minimal YAML subset behind the local-file adapter seam."""
    records = _records_module()
    path = tmp_path / "cases.yaml"
    path.write_text(
        """
cases:
  -
    case_id: case-empty-expected
    source_refs:
      - ground_truth.json:sha256:metadata
    expected_findings: []
""".lstrip(),
    )

    loaded = records.load_structured_records(path, root_key="cases")

    assert loaded == (
        {
            "case_id": "case-empty-expected",
            "source_refs": ["ground_truth.json:sha256:metadata"],
            "expected_findings": [],
        },
    )


def test_loads_rootless_yaml_structured_records(tmp_path: Path) -> None:
    """Locks root_key=None parity between JSON and minimal YAML records."""
    records = _records_module()
    path = tmp_path / "records.yaml"
    path.write_text(
        """
- case_id: case-1
  source_refs: []
- case_id: case-2
  source_refs: []
""".lstrip(),
    )

    loaded = records.load_structured_records(path)

    assert loaded == (
        {"case_id": "case-1", "source_refs": []},
        {"case_id": "case-2", "source_refs": []},
    )


def test_loads_yaml_inline_sequences_with_quoted_scalars(tmp_path: Path) -> None:
    """Locks real YAML parser behavior for common compact case fixtures."""
    records = _records_module()
    path = tmp_path / "cases.yaml"
    path.write_text(
        """
cases:
  - case_id: case-inline
    source_refs: ["ground_truth.json:sha256:metadata", "patch.diff:sha256:local-input"]
    labels: ["business-rule", "yaml-inline"]
""".lstrip(),
    )

    loaded = records.load_structured_records(path, root_key="cases")

    assert loaded == (
        {
            "case_id": "case-inline",
            "source_refs": [
                "ground_truth.json:sha256:metadata",
                "patch.diff:sha256:local-input",
            ],
            "labels": ["business-rule", "yaml-inline"],
        },
    )


def test_rejects_non_mapping_records(tmp_path: Path) -> None:
    """Prevents callers from validating scalar/list records as domain objects."""
    records = _records_module()
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(["not", "a", "mapping"]) + "\n")

    with pytest.raises(ValueError, match="records must be mappings"):
        records.load_structured_records(path)


def test_malformed_yaml_error_does_not_leak_raw_line(tmp_path: Path) -> None:
    """Locks sanitized parse errors at the adapter seam."""
    records = _records_module()
    path = tmp_path / "private.yaml"
    path.write_text(
        """
cases:
  - case_id: case-malformed-private-yaml
    diff --git a/src/service.py b/src/service.py
""".lstrip(),
    )

    with pytest.raises(ValueError) as error:
        records.load_structured_records(path, root_key="cases")

    message = str(error.value)
    assert "YAML" in message
    assert "diff --git" not in message
    assert "service.py" not in message
