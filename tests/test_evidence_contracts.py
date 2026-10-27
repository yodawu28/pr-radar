from importlib import import_module

import pytest
from pydantic import ValidationError


def _contracts_module():
    return import_module("pr_radar.contracts")


def _pr_input(contracts):
    return contracts.PrInput(
        provider="github",
        deployment="github_self_hosted",
        repository="arkdevelopers/code-review-agent",
        pull_request_number=59,
        url="https://git.linecorp.com/arkdevelopers/code-review-agent/pull/59",
    )


def test_evidence_pack_separates_raw_local_data_from_report_safe_evidence() -> None:
    """Catches reports or summaries that can accidentally persist raw diff/source."""
    contracts = _contracts_module()
    pr_input = _pr_input(contracts)

    pr_metadata = contracts.PrMetadata(
        title="Add generated review helper",
        body="Generated with Claude Code\napi_key=secret-token",
        author_login="alice",
        head_ref="cursor/review-helper",
        base_ref="main",
        labels=["agent-pr"],
    )
    commit = contracts.CommitMetadata(
        sha="abc1234",
        author_login="devin[bot]",
        committer_login="github-actions[bot]",
        message="Generate review helper",
    )
    changed_file = contracts.ChangedFileMetadata(
        path="src/review.py",
        status="modified",
        additions=12,
        deletions=3,
    )
    raw_evidence = contracts.RawEvidence(
        diff="diff --git a/src/review.py b/src/review.py\n+TOKEN=secret-token",
        file_contents={"src/review.py": "TOKEN=secret-token"},
    )
    evidence_ref = contracts.EvidenceReference(
        kind="diff",
        ref="diff:src/review.py",
    )
    redacted_excerpt = contracts.RedactedExcerpt(
        evidence_ref=evidence_ref,
        text="+TOKEN=<REDACTED>",
    )

    evidence_pack = contracts.PrEvidencePack(
        pr_input=pr_input,
        pr_metadata=pr_metadata,
        commits=[commit],
        changed_files=[changed_file],
        raw_evidence=raw_evidence,
        evidence_refs=[evidence_ref],
        redacted_excerpts=[redacted_excerpt],
    )

    assert evidence_pack.commits == (commit,)
    assert evidence_pack.changed_files == (changed_file,)
    assert evidence_pack.evidence_refs == (evidence_ref,)
    assert evidence_pack.redacted_excerpts == (redacted_excerpt,)
    assert evidence_pack.raw_evidence.diff.startswith("diff --git")
    assert redacted_excerpt.text == "+TOKEN=<REDACTED>"

    dumped = evidence_pack.model_dump()
    assert "raw_evidence" in dumped
    assert "raw_diff" not in dumped["redacted_excerpts"][0]

    with pytest.raises(ValidationError):
        contracts.RedactedExcerpt(
            evidence_ref=evidence_ref,
            text="+TOKEN=<REDACTED>",
            raw_diff="diff --git a/private.py b/private.py",
        )


def test_fetch_failure_contract_uses_fixed_fail_closed_categories() -> None:
    """Catches free-form fetch failures that cannot drive deterministic CLI exits."""
    contracts = _contracts_module()

    failure = contracts.FetchFailure(
        reason="missing_token",
        message="Missing GHE_TOKEN for self-hosted GitHub.",
    )

    assert failure.reason == "missing_token"
    assert failure.message == "Missing GHE_TOKEN for self-hosted GitHub."

    for reason in (
        "missing_token",
        "unauthorized",
        "forbidden",
        "not_found",
        "timeout",
        "rate_limited",
        "unsupported_provider",
        "unsupported_deployment",
    ):
        assert contracts.FetchFailure(reason=reason, message=reason).reason == reason

    with pytest.raises(ValidationError):
        contracts.FetchFailure(reason="try_again_later", message="retry")

    with pytest.raises(ValidationError):
        contracts.FetchFailure(
            reason="unauthorized",
            message="Unauthorized",
            token="ghp_secret",
        )


def test_changed_file_status_uses_github_compatible_serialized_vocabulary() -> None:
    """Catches accidental translation from GitHub `removed` to Git `deleted`."""
    contracts = _contracts_module()

    removed_file = contracts.ChangedFileMetadata(
        path="src/old.py",
        status="removed",
        additions=0,
        deletions=12,
    )

    assert removed_file.status == "removed"
    assert removed_file.model_dump()["status"] == "removed"

    with pytest.raises(ValidationError):
        contracts.ChangedFileMetadata(
            path="src/old.py",
            status="deleted",
            additions=0,
            deletions=12,
        )


def test_ai_signal_finding_contract_keeps_weak_repo_markers_visible() -> None:
    """Catches AI-signal contracts that cannot represent weak project-level markers."""
    contracts = _contracts_module()
    evidence_ref = contracts.EvidenceReference(kind="repo_file", ref="file:AGENTS.md")
    excerpt = contracts.RedactedExcerpt(
        evidence_ref=evidence_ref,
        text="Agent operating guide present.",
    )

    signal = contracts.AiSignalFinding(
        signal_type="repo_marker",
        strength="weak",
        title="Repository contains agent instructions",
        status="info",
        score=35,
        confidence=0.35,
        evidence_refs=[evidence_ref],
        redacted_excerpts=[excerpt],
        decision_source="deterministic",
        calibration_reason="repo_marker_weak_project_level_signal",
        tags=[contracts.LOW_CONFIDENCE_TAG],
    )

    assert signal.signal_type == "repo_marker"
    assert signal.strength == "weak"
    assert signal.status == "info"
    assert signal.score == 35
    assert signal.confidence == 0.35
    assert signal.evidence_refs == (evidence_ref,)
    assert signal.redacted_excerpts == (excerpt,)
    assert signal.calibration_reason == "repo_marker_weak_project_level_signal"
    assert signal.tags == (contracts.LOW_CONFIDENCE_TAG,)

    with pytest.raises(ValidationError):
        contracts.AiSignalFinding(
            signal_type="repo_marker",
            strength="definitive",
            title="Repository contains agent instructions",
            status="info",
            score=35,
            confidence=0.35,
            evidence_refs=[evidence_ref],
            redacted_excerpts=[excerpt],
            decision_source="deterministic",
            calibration_reason="repo_marker_weak_project_level_signal",
            tags=[contracts.LOW_CONFIDENCE_TAG],
        )
