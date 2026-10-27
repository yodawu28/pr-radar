from importlib import import_module, util

from pr_radar.contracts import (
    BlastRadiusBudget,
    BlastRadiusDependent,
    BlastRadiusSummary,
    EvidenceReference,
    Finding,
    RedactedExcerpt,
)
from pr_radar.scan import scan_pr


def _context_module():
    assert util.find_spec("pr_radar.application.context") is not None, (
        "expected pr_radar.application.context to provide the minimum "
        "context-layer boundary"
    )
    return import_module("pr_radar.application.context")


def _dependency_finding() -> Finding:
    return Finding(
        id="dependency.added.requests",
        pillar="security_supply_chain",
        title="New dependency requires supply-chain review",
        status="warning",
        score=68,
        confidence=0.74,
        evidence_refs=("file:pyproject.toml", "diff:pyproject.toml"),
        decision_source="deterministic",
        calibration_reason="dependency_added_manifest_requires_supply_chain_review",
        tags=("detector:dependency",),
    )


def test_context_envelope_carries_report_safe_finding_context() -> None:
    """Locks the minimum payload Sprint 4 decision layers may consume."""
    context = _context_module()

    envelope = context.build_context_envelope(
        findings=(_dependency_finding(),),
        detector_id="dependency",
        max_chars=1_200,
        redacted_excerpts_by_finding_id={
            "dependency.added.requests": (
                '+ requests = "<REDACTED_SECRET>"',
            ),
        },
    )

    assert envelope.context_grade == "review_grade"
    assert envelope.budget.max_chars == 1_200
    assert envelope.budget.used_chars <= envelope.budget.max_chars
    assert envelope.budget.is_over_budget is False
    assert envelope.omitted_finding_ids == ()

    assert len(envelope.items) == 1
    item = envelope.items[0]
    assert item.finding_id == "dependency.added.requests"
    assert item.detector_id == "dependency"
    assert item.pillar == "security_supply_chain"
    assert item.evidence_refs == ("file:pyproject.toml", "diff:pyproject.toml")
    assert item.calibration_reason == (
        "dependency_added_manifest_requires_supply_chain_review"
    )
    assert item.redacted_excerpts == ('+ requests = "<REDACTED_SECRET>"',)

    serialized = str(envelope.model_dump())
    assert "raw diff" not in serialized.lower()
    assert "PRIVATE_RAW_SOURCE" not in serialized
    assert "sk_live_1234567890abcdef" not in serialized


def test_context_envelope_marks_oversized_context_over_budget() -> None:
    """Prevents silent token stuffing when detector evidence grows."""
    context = _context_module()

    envelope = context.build_context_envelope(
        findings=(_dependency_finding(),),
        detector_id="dependency",
        max_chars=64,
        redacted_excerpts_by_finding_id={
            "dependency.added.requests": ("safe excerpt " * 40,),
        },
    )

    assert envelope.budget.max_chars == 64
    assert envelope.budget.is_over_budget is True
    assert envelope.omitted_finding_ids == ("dependency.added.requests",)
    assert envelope.items == ()


def test_context_envelope_redacts_excerpt_inputs_at_boundary() -> None:
    """Prevents detectors from leaking unredacted content into model context."""
    context = _context_module()

    envelope = context.build_context_envelope(
        findings=(_dependency_finding(),),
        detector_id="dependency",
        max_chars=1_200,
        redacted_excerpts_by_finding_id={
            "dependency.added.requests": (
                "api_key=sk_live_1234567890abcdef "
                "https://git.linecorp.com/team/private/pull/1 "
                "owner@example.com",
            ),
        },
    )

    assert envelope.items[0].redacted_excerpts == (
        "api_key=<REDACTED_SECRET> "
        "https://<REDACTED_INTERNAL_URL> "
        "<REDACTED_EMAIL>",
    )
    serialized = str(envelope.model_dump())
    assert "sk_live_1234567890abcdef" not in serialized
    assert "git.linecorp.com/team/private" not in serialized
    assert "owner@example.com" not in serialized


def test_context_envelope_preserves_excerpts_for_repeated_stable_finding_ids() -> None:
    """Prevents duplicate rule findings from overwriting each other's excerpts."""
    context = _context_module()
    evidence_ref = EvidenceReference(kind="diff", ref="diff:tests/test_a.py")
    first = Finding(
        id="test_shape.disabled_test",
        pillar="test_integrity",
        title="Disabled test requires review",
        status="warning",
        score=66,
        confidence=0.68,
        evidence_refs=("file:tests/test_a.py", "diff:tests/test_a.py"),
        decision_source="deterministic",
        calibration_reason="disabled_test_reduces_test_integrity",
        tags=("detector:test_shape", "test:disabled"),
        redacted_excerpts=(
            RedactedExcerpt(evidence_ref=evidence_ref, text="+@pytest.mark.skip"),
        ),
    )
    second = Finding(
        id="test_shape.disabled_test",
        pillar="test_integrity",
        title="Disabled test requires review",
        status="warning",
        score=66,
        confidence=0.68,
        evidence_refs=("file:tests/test_b.py", "diff:tests/test_b.py"),
        decision_source="deterministic",
        calibration_reason="disabled_test_reduces_test_integrity",
        tags=("detector:test_shape", "test:disabled"),
        redacted_excerpts=(
            RedactedExcerpt(evidence_ref=evidence_ref, text="+test.skip"),
        ),
    )

    envelope = context.build_context_envelope(
        findings=(first, second),
        detector_id="test_shape",
        max_chars=2_000,
    )

    assert tuple(item.redacted_excerpts for item in envelope.items) == (
        ("+@pytest.mark.skip",),
        ("+test.skip",),
    )


def test_context_envelope_carries_blast_radius_advisory_context_raw_free() -> None:
    """Keeps downstream context available for Sprint 4 without raw source."""
    context = _context_module()
    blast_radius_summary = BlastRadiusSummary(
        availability="available",
        reason_code="local_workspace_python_imports",
        changed_paths=("src/service.py",),
        direct_dependents=(
            BlastRadiusDependent(
                changed_path="src/service.py",
                dependent_path="src/api.py",
                import_ref="from src.service import Service",
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

    envelope = context.build_context_envelope(
        findings=(_dependency_finding(),),
        detector_id="dependency",
        max_chars=2_000,
        blast_radius_summary=blast_radius_summary,
    )

    assert envelope.blast_radius_summary == blast_radius_summary
    serialized = str(envelope.model_dump(mode="json"))
    assert "src/api.py" in serialized
    assert "from src.service import Service" in serialized
    assert "PRIVATE_RAW_SOURCE" not in serialized
    assert "sk_live_1234567890abcdef" not in serialized
    assert "diff --git" not in serialized


def test_parser_only_scan_does_not_claim_review_grade_context() -> None:
    """Parser-only URL handling must stay an identity/smoke path."""
    report = scan_pr("https://github.com/example/repo/pull/17")

    assert report.evaluation_metadata["context_grade"] == "parser_only"
    assert report.evaluation_metadata["context_envelope"] == "unavailable"
    assert report.evaluation_metadata["blast_radius_context_grade"] == "parser_only"
    assert report.evaluation_metadata["blast_radius_availability"] == "unavailable"
    assert report.evaluation_metadata["blast_radius_reason_code"] == "parser_only"
