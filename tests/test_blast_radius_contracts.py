from importlib import import_module

import pytest
from pydantic import ValidationError


def _contracts_module():
    try:
        return import_module("pr_radar.contracts")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.contracts module: {error}")


def _blast_radius_contracts():
    contracts = _contracts_module()
    missing = tuple(
        name
        for name in (
            "BlastRadiusSummary",
            "BlastRadiusDependent",
            "BlastRadiusBudget",
        )
        if not hasattr(contracts, name)
    )

    assert missing == (), (
        "expected blast-radius contract names exported by pr_radar.contracts: "
        f"{missing}"
    )
    return (
        contracts,
        contracts.BlastRadiusSummary,
        contracts.BlastRadiusDependent,
        contracts.BlastRadiusBudget,
    )


def test_blast_radius_summary_is_advisory_contract_not_finding() -> None:
    """Catches modeling blast-radius context as a risk finding."""
    (
        contracts,
        BlastRadiusSummary,
        BlastRadiusDependent,
        BlastRadiusBudget,
    ) = _blast_radius_contracts()

    summary = BlastRadiusSummary(
        availability="available",
        reason_code="local_workspace_python_imports",
        changed_paths=("src/app/service.py",),
        direct_dependents=(
            BlastRadiusDependent(
                changed_path="src/app/service.py",
                dependent_path="src/app/api.py",
                import_ref="from app.service import UserService",
            ),
        ),
        dependent_count=1,
        budget=BlastRadiusBudget(
            max_dependents=25,
            emitted_dependents=1,
            omitted_dependents=0,
        ),
        truncated=False,
    )

    assert not issubclass(BlastRadiusSummary, contracts.Finding)
    assert summary.availability == "available"
    assert summary.reason_code == "local_workspace_python_imports"
    assert summary.changed_paths == ("src/app/service.py",)
    assert summary.direct_dependents[0].dependent_path == "src/app/api.py"
    assert summary.dependent_count == 1
    assert summary.budget.max_dependents == 25
    assert summary.truncated is False


def test_blast_radius_summary_represents_source_absent_unavailable_state() -> None:
    """Catches parser-only or source-absent scans claiming blast-radius coverage."""
    (
        _contracts,
        BlastRadiusSummary,
        _BlastRadiusDependent,
        BlastRadiusBudget,
    ) = _blast_radius_contracts()

    summary = BlastRadiusSummary(
        availability="unavailable",
        reason_code="requires_local_workspace",
        changed_paths=("src/app/service.py",),
        direct_dependents=(),
        dependent_count=0,
        budget=BlastRadiusBudget(
            max_dependents=25,
            emitted_dependents=0,
            omitted_dependents=0,
        ),
        truncated=False,
    )

    assert summary.availability == "unavailable"
    assert summary.reason_code == "requires_local_workspace"
    assert summary.direct_dependents == ()
    assert summary.dependent_count == 0


def test_blast_radius_summary_carries_deterministic_budget_metadata() -> None:
    """Catches ambiguous context trimming that hides downstream impact counts."""
    (
        _contracts,
        BlastRadiusSummary,
        BlastRadiusDependent,
        BlastRadiusBudget,
    ) = _blast_radius_contracts()

    summary = BlastRadiusSummary(
        availability="partial",
        reason_code="budget_truncated",
        changed_paths=("src/app/service.py",),
        direct_dependents=(
            BlastRadiusDependent(
                changed_path="src/app/service.py",
                dependent_path="src/app/api.py",
                import_ref="from app.service import UserService",
            ),
        ),
        dependent_count=4,
        budget=BlastRadiusBudget(
            max_dependents=1,
            emitted_dependents=1,
            omitted_dependents=3,
        ),
        truncated=True,
    )

    assert summary.availability == "partial"
    assert summary.reason_code == "budget_truncated"
    assert summary.dependent_count == 4
    assert len(summary.direct_dependents) == 1
    assert summary.budget.emitted_dependents == 1
    assert summary.budget.omitted_dependents == 3
    assert summary.truncated is True


def test_blast_radius_summary_rejects_raw_diff_and_source_fields() -> None:
    """Prevents advisory context from becoming a raw source transport."""
    (
        _contracts,
        BlastRadiusSummary,
        BlastRadiusDependent,
        BlastRadiusBudget,
    ) = _blast_radius_contracts()

    with pytest.raises(ValidationError):
        BlastRadiusDependent(
            changed_path="src/app/service.py",
            dependent_path="src/app/api.py",
            import_ref="from app.service import UserService",
            source_excerpt="from app.service import UserService",
        )

    with pytest.raises(ValidationError):
        BlastRadiusSummary(
            availability="available",
            reason_code="local_workspace_python_imports",
            changed_paths=("src/app/service.py",),
            direct_dependents=(),
            dependent_count=0,
            budget=BlastRadiusBudget(
                max_dependents=25,
                emitted_dependents=0,
                omitted_dependents=0,
            ),
            truncated=False,
            raw_diff="diff --git a/src/app/service.py b/src/app/service.py",
        )

    with pytest.raises(ValidationError):
        BlastRadiusSummary(
            availability="available",
            reason_code="local_workspace_python_imports",
            changed_paths=("src/app/service.py",),
            direct_dependents=(),
            dependent_count=0,
            budget=BlastRadiusBudget(
                max_dependents=25,
                emitted_dependents=0,
                omitted_dependents=0,
            ),
            truncated=False,
            raw_source="class PrivateImplementation: ...",
        )
