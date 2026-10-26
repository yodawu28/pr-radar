from pr_radar.contracts import (
    EvidenceReference,
    Finding,
    PrInput,
    RedactedExcerpt,
    Report,
)
from pr_radar.report_renderer import render_text_report


def test_render_text_report_includes_baseline_radar_sections() -> None:
    """Catches reports that omit the baseline executive radar shape."""
    report = Report(
        overall_status="safe",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="No AI-generation evidence collected yet.",
    )

    rendered = render_text_report(report)

    assert "PR Radar Local Report" in rendered
    assert "Overall Status: safe" in rendered
    assert "PR: example/repo#17" in rendered
    assert "URL: https://github.com/example/repo/pull/17" in rendered
    assert "AI Signal: No AI-generation evidence collected yet." in rendered
    assert "Security & Supply Chain: No findings yet." in rendered
    assert "Deployment & Downtime: No findings yet." in rendered
    assert "Blast Radius & Downstream: No findings yet." in rendered
    assert "Performance & Footprint: No findings yet." in rendered
    assert "Anti-Bloat & DRY: No findings yet." in rendered
    assert "Test Integrity & Edge Cases: No findings yet." in rendered
    assert "Rollback & Feature Flags: No findings yet." in rendered
    assert "nitpick" not in rendered.lower()


def test_render_text_report_labels_low_confidence_findings() -> None:
    """Catches renderers that hide weak evidence instead of labeling it."""
    low_confidence_finding = Finding(
        id="finding-test-001",
        pillar="test_integrity",
        title="Generated test only checks mocks",
        status="warning",
        score=55,
        confidence=0.42,
        evidence_refs=["tests/test_service.py:12"],
        decision_source="deterministic",
        tags=["low confidence"],
    )
    report = Report(
        overall_status="needs_attention",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="Possible AI-assisted changes, evidence is weak.",
        findings=[low_confidence_finding],
        low_confidence_findings=[low_confidence_finding],
    )

    rendered = render_text_report(report)

    assert "Low Confidence Findings" in rendered
    assert "finding-test-001" in rendered
    assert "Generated test only checks mocks" in rendered
    assert "low confidence" in rendered
    assert "tests/test_service.py:12" in rendered


def test_render_text_report_keeps_unknown_pillar_findings_visible() -> None:
    """Catches renderers that silently drop future or malformed pillars."""
    unknown_pillar_finding = Finding(
        id="finding-future-001",
        pillar="unknown_future_pillar",
        title="Future detector found a risk",
        status="high",
        score=82,
        confidence=0.73,
        evidence_refs=["src/future.py:9"],
        decision_source="deterministic",
        tags=[],
    )
    report = Report(
        overall_status="high_risk",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="No AI-generation evidence collected yet.",
        findings=[unknown_pillar_finding],
    )

    rendered = render_text_report(report)

    assert "Other Findings" in rendered
    assert "finding-future-001" in rendered
    assert "Future detector found a risk" in rendered
    assert "unknown_future_pillar" in rendered
    assert "src/future.py:9" in rendered


def test_render_text_report_with_redacted_summary_does_not_print_raw_secret() -> None:
    """Catches report paths that bypass redaction before rendering excerpts."""
    report = Report(
        overall_status="needs_attention",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="+ api_key=sk_live_1234567890abcdef",
    )

    rendered = render_text_report(report)

    assert "api_key=<REDACTED_SECRET>" in rendered
    assert "sk_live_1234567890abcdef" not in rendered


def test_render_text_report_includes_redacted_finding_excerpts() -> None:
    """Catches terminal reports that hide the evidence needed to trust findings."""
    finding = Finding(
        id="test_shape.disabled_test",
        pillar="test_integrity",
        title="Disabled test requires review",
        status="warning",
        score=66,
        confidence=0.68,
        evidence_refs=["file:tests/test_payments.py", "diff:tests/test_payments.py"],
        decision_source="deterministic",
        redacted_excerpts=[
            RedactedExcerpt(
                evidence_ref=EvidenceReference(
                    kind="diff",
                    ref="diff:tests/test_payments.py",
                ),
                text='+@pytest.mark.skip(reason="flaky api_key=sk_live_123456")',
            ),
        ],
    )
    report = Report(
        overall_status="needs_attention",
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        ai_signal_summary="No AI-generation evidence detected.",
        findings=[finding],
    )

    rendered = render_text_report(report)

    assert "excerpt=" in rendered
    assert "pytest.mark.skip" in rendered
    assert "api_key=<REDACTED_SECRET>" in rendered
    assert "sk_live_123456" not in rendered
