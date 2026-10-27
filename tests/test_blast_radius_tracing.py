from importlib import import_module
from pathlib import Path

import pytest


def _blast_radius_module():
    try:
        return import_module("pr_radar.application.blast_radius")
    except ModuleNotFoundError as error:
        pytest.fail(
            "expected pr_radar.application.blast_radius to provide the "
            f"local workspace one-hop tracing boundary: {error}",
        )


def _write_file(workspace_path: Path, relative_path: str, content: str) -> None:
    file_path = workspace_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def test_python_one_hop_tracer_reports_direct_import_dependents(
    tmp_path: Path,
) -> None:
    """Locks the useful MVP: changed a.py and b.py importing it."""
    blast_radius = _blast_radius_module()
    _write_file(
        tmp_path,
        "a.py",
        "class Foo:\n"
        "    def answer(self) -> int:\n"
        "        return 42\n",
    )
    _write_file(
        tmp_path,
        "b.py",
        "from a import Foo\n\n"
        "def build() -> Foo:\n"
        "    return Foo()\n",
    )

    summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("a.py",),
        max_dependents=25,
    )

    assert summary.availability == "available"
    assert summary.reason_code == "local_workspace_python_imports"
    assert summary.changed_paths == ("a.py",)
    assert summary.dependent_count == 1
    assert summary.truncated is False
    assert len(summary.direct_dependents) == 1
    dependent = summary.direct_dependents[0]
    assert dependent.changed_path == "a.py"
    assert dependent.dependent_path == "b.py"
    assert dependent.import_ref == "from a import Foo"


def test_python_one_hop_tracer_suppresses_unrelated_files_and_raw_source(
    tmp_path: Path,
) -> None:
    """Prevents context bloat and raw source transport in the summary."""
    blast_radius = _blast_radius_module()
    _write_file(tmp_path, "a.py", "PRIVATE_RAW_SOURCE = 'do not serialize'\n")
    _write_file(tmp_path, "b.py", "from a import PRIVATE_RAW_SOURCE\n")
    _write_file(tmp_path, "other.py", "class Other:\n    pass\n")
    _write_file(tmp_path, "unrelated.py", "from other import Other\n")

    summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("a.py",),
        max_dependents=25,
    )

    assert tuple(
        dependent.dependent_path for dependent in summary.direct_dependents
    ) == ("b.py",)
    serialized = str(summary.model_dump(mode="json"))
    assert "unrelated.py" not in serialized
    assert "PRIVATE_RAW_SOURCE = 'do not serialize'" not in serialized
    assert "class Other" not in serialized


def test_python_one_hop_tracer_degrades_for_missing_or_unsupported_changed_files(
    tmp_path: Path,
) -> None:
    """Covers deleted/renamed paths and unsupported language inputs."""
    blast_radius = _blast_radius_module()
    _write_file(tmp_path, "consumer.py", "from missing import Foo\n")
    _write_file(tmp_path, "service.ts", "export class Service {}\n")

    missing_summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("missing.py",),
        max_dependents=25,
    )
    unsupported_summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("service.ts",),
        max_dependents=25,
    )

    assert missing_summary.availability in {"partial", "unavailable"}
    assert "missing" in missing_summary.reason_code
    assert missing_summary.direct_dependents == ()
    assert missing_summary.dependent_count == 0

    assert unsupported_summary.availability in {"partial", "unavailable"}
    assert "unsupported" in unsupported_summary.reason_code
    assert unsupported_summary.direct_dependents == ()
    assert unsupported_summary.dependent_count == 0


def test_python_one_hop_tracer_does_not_claim_dynamic_import_dependents(
    tmp_path: Path,
) -> None:
    """Dynamic imports may be noted later, but not as confident 1-hop edges."""
    blast_radius = _blast_radius_module()
    _write_file(tmp_path, "a.py", "class Foo:\n    pass\n")
    _write_file(
        tmp_path,
        "dynamic_consumer.py",
        "import importlib\n"
        "module = importlib.import_module('a')\n"
        "Foo = module.Foo\n",
    )

    summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("a.py",),
        max_dependents=25,
    )

    assert "dynamic" in summary.reason_code or summary.availability == "available"
    assert summary.direct_dependents == ()
    assert summary.dependent_count == 0


def test_python_one_hop_tracer_trims_dependents_with_stable_changed_path_order(
    tmp_path: Path,
) -> None:
    """Locks deterministic budget behavior before report/context integration."""
    blast_radius = _blast_radius_module()
    _write_file(tmp_path, "a.py", "class A:\n    pass\n")
    _write_file(tmp_path, "b.py", "class B:\n    pass\n")
    _write_file(
        tmp_path,
        "aa_consumer.py",
        "PRIVATE_OMITTED_SOURCE = 'do not serialize'\nfrom a import A\n",
    )
    _write_file(tmp_path, "ab_consumer.py", "from a import A\n")
    _write_file(tmp_path, "ba_consumer.py", "from b import B\n")
    _write_file(tmp_path, "bb_consumer.py", "from b import B\n")

    summary = blast_radius.trace_blast_radius(
        workspace_path=tmp_path,
        changed_paths=("b.py", "a.py"),
        max_dependents=2,
    )

    assert summary.availability == "partial"
    assert summary.reason_code == "budget_truncated"
    assert summary.changed_paths == ("b.py", "a.py")
    assert summary.dependent_count == 4
    assert summary.truncated is True
    assert summary.budget.max_dependents == 2
    assert summary.budget.emitted_dependents == 2
    assert summary.budget.omitted_dependents == 2
    assert tuple(
        (dependent.changed_path, dependent.dependent_path)
        for dependent in summary.direct_dependents
    ) == (
        ("b.py", "ba_consumer.py"),
        ("b.py", "bb_consumer.py"),
    )

    serialized = str(summary.model_dump(mode="json"))
    assert "aa_consumer.py" not in serialized
    assert "PRIVATE_OMITTED_SOURCE = 'do not serialize'" not in serialized
