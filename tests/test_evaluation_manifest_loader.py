import json
from importlib import import_module
from pathlib import Path

import pytest


def _loader_module():
    try:
        return import_module("pr_radar.evaluation.manifest_loader")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.evaluation.manifest_loader: {error}")


def test_loads_jsonl_ground_truth_manifest_from_bench_cases(tmp_path: Path) -> None:
    """Catches evaluation loaders that require live PR fetch or private repos."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "cases.jsonl"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "case-01-biz-immutable-amount",
                "source_format": "aimigo_bench_case",
                "pr_id": "case-01-biz-immutable-amount",
                "stack": "java-spring",
                "ruleset_version": "0.1.0",
                "labels": ["business-rule"],
                "source_refs": [
                    "ground_truth.json:sha256:metadata",
                    "patch.diff:sha256:local-input",
                ],
                "expected_findings": [
                    {
                        "finding_id": "expected:java.spring.biz.immutable_amount",
                        "pillar": "security_supply_chain",
                        "reason_code": "immutable_amount_violation",
                        "evidence_path": (
                            "src/main/java/com/acme/orders/OrderService.java"
                        ),
                        "severity": "high_risk",
                        "source_rule_id": "java.spring.biz.immutable_amount",
                        "source_line": 16,
                        "source_excerpt_hash": "sha256:expected-evidence",
                    },
                ],
            },
        )
        + "\n",
    )

    cases = loader.load_evaluation_manifest(manifest_path)

    assert len(cases) == 1
    assert cases[0].case_id == "case-01-biz-immutable-amount"
    assert cases[0].expected_findings[0].source_rule_id == (
        "java.spring.biz.immutable_amount"
    )


def test_loads_yaml_ground_truth_manifest_from_bench_cases(tmp_path: Path) -> None:
    """Catches JSONL-only loaders before Sprint 5 accepts YAML manifests."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "cases.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
cases:
  - case_id: case-78-challenge-5-files
    source_format: aimigo_bench_case
    pr_id: case-78-challenge-5-files
    stack: null
    ruleset_version: null
    source_refs:
      - ground_truth.json:sha256:partial-metadata
    partial_fields:
      - stack
      - ruleset_version
    expected_findings:
      - finding_id: expected:partial:case-78
        pillar: test_integrity
        reason_code: unmapped_external_rule
        evidence_path: tests/test_checkout.py
        severity: warning
        partial_fields:
          - ruleId
          - title
          - evidence
        unavailable_fields:
          - source_rule_id
""".lstrip(),
    )

    cases = loader.load_evaluation_manifest(manifest_path)

    assert len(cases) == 1
    assert cases[0].partial_fields == ("stack", "ruleset_version")
    assert cases[0].expected_findings[0].partial_fields == (
        "ruleId",
        "title",
        "evidence",
    )


def test_loads_yaml_manifest_with_split_list_item_and_inline_empty_list(
    tmp_path: Path,
) -> None:
    """Catches valid YAML case shapes used by hand-authored bench manifests."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "cases.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
cases:
  -
    case_id: case-empty-expected
    source_format: aimigo_bench_case
    pr_id: case-empty-expected
    source_refs:
      - ground_truth.json:sha256:metadata
    expected_findings: []
""".lstrip(),
    )

    cases = loader.load_evaluation_manifest(manifest_path)

    assert len(cases) == 1
    assert cases[0].case_id == "case-empty-expected"
    assert cases[0].expected_findings == ()


def test_invalid_manifest_schema_exits_non_zero_for_cli_adapter(
    tmp_path: Path,
) -> None:
    """Catches invalid suite configs being treated as empty successful suites."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "bad.jsonl"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "case-missing-required-fields",
                "source_format": "aimigo_bench_case",
            },
        )
        + "\n",
    )

    with pytest.raises(SystemExit) as error:
        loader.load_evaluation_manifest_or_exit(manifest_path)

    assert error.value.code != 0


@pytest.mark.parametrize(
    "payload",
    (
        {
            "case_id": "case-raw-diff",
            "source_format": "aimigo_bench_case",
            "pr_id": "case-raw-diff",
            "source_refs": ["diff --git a/src/service.py b/src/service.py"],
            "expected_findings": [],
        },
        {
            "case_id": "case-secret",
            "source_format": "aimigo_bench_case",
            "pr_id": "case-secret",
            "labels": ["password=secret-token"],
            "source_refs": ["ground_truth.json:sha256:metadata"],
            "expected_findings": [],
        },
        {
            "case_id": "case-internal-url",
            "source_format": "aimigo_bench_case",
            "pr_id": "case-internal-url",
            "labels": ["https://git.linecorp.com/team/private-repo"],
            "source_refs": ["ground_truth.json:sha256:metadata"],
            "expected_findings": [],
        },
        {
            "case_id": "case-raw-source",
            "source_format": "aimigo_bench_case",
            "pr_id": "case-raw-source",
            "labels": ["class Secret: pass"],
            "source_refs": ["ground_truth.json:sha256:metadata"],
            "expected_findings": [],
        },
    ),
)
def test_manifest_loader_rejects_raw_private_content(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    """Catches raw diff/source/secrets/internal URLs before contract creation."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "private.jsonl"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(payload) + "\n")

    with pytest.raises(loader.EvaluationManifestLoadError):
        loader.load_evaluation_manifest(manifest_path)


def test_manifest_loader_rejects_raw_private_content_in_mapping_keys_without_leak(
    tmp_path: Path,
) -> None:
    """Catches raw/private mapping keys leaking through schema errors."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "private.jsonl"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "case-private-key",
                "source_format": "aimigo_bench_case",
                "pr_id": "case-private-key",
                "source_refs": ["ground_truth.json:sha256:metadata"],
                "expected_findings": [],
                "https://git.linecorp.com/team/private-repo": "metadata",
            },
        )
        + "\n",
    )

    with pytest.raises(loader.EvaluationManifestLoadError) as error:
        loader.load_evaluation_manifest(manifest_path)

    message = str(error.value)
    assert "content-free" in message
    assert "git.linecorp.com" not in message
    assert "private-repo" not in message


def test_manifest_loader_rejects_malformed_yaml_without_raw_line_leak(
    tmp_path: Path,
) -> None:
    """Catches parser syntax errors that echo raw source/diff lines."""
    loader = _loader_module()
    manifest_path = tmp_path / "evaluation" / "bench" / "cases" / "private.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
cases:
  - case_id: case-malformed-private-yaml
    source_format: aimigo_bench_case
    pr_id: case-malformed-private-yaml
    diff --git a/src/service.py b/src/service.py
""".lstrip(),
    )

    with pytest.raises(loader.EvaluationManifestLoadError) as error:
        loader.load_evaluation_manifest(manifest_path)

    message = str(error.value)
    assert "YAML manifest" in message
    assert "diff --git" not in message
    assert "service.py" not in message
