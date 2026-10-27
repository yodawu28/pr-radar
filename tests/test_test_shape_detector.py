from pr_radar.contracts import (
    ChangedFileMetadata,
    LOW_CONFIDENCE_TAG,
    PrEvidencePack,
    PrInput,
    PrMetadata,
    RawEvidence,
)
from pr_radar.detectors.static_risk import run_static_detectors
from pr_radar.detectors.test_integrity.test_shape import detect_test_shape_risks
from pr_radar.privacy.redaction import MAX_REDACTED_EXCERPT_LENGTH


def _changed_file(path: str, diff: str, status: str = "modified") -> ChangedFileMetadata:
    return ChangedFileMetadata(
        path=path,
        status=status,
        additions=diff.count("\n+"),
        deletions=diff.count("\n-"),
    )


def _evidence_pack(
    *,
    changed_files: tuple[ChangedFileMetadata, ...],
    diff: str,
    file_contents: dict[str, str] | None = None,
) -> PrEvidencePack:
    return PrEvidencePack(
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        pr_metadata=PrMetadata(
            title="Update payment retry behavior",
            body="",
            author_login="alice",
            head_ref="agent/payment-retry",
            base_ref="main",
        ),
        changed_files=changed_files,
        raw_evidence=RawEvidence(
            diff=diff,
            file_contents=file_contents or {},
        ),
    )


def test_test_shape_detector_flags_behavior_change_without_tests() -> None:
    """Catches behavior changes that arrive without nearby test evidence."""
    source_diff = (
        "diff --git a/src/payments/service.py b/src/payments/service.py\n"
        "@@ def charge(request): @@\n"
        "+    if request.retry_count > 3:\n"
        '+        raise PaymentRetryLimitExceeded("retry limit reached")\n'
    )
    result = run_static_detectors(
        _evidence_pack(
            changed_files=(_changed_file("src/payments/service.py", source_diff),),
            diff=source_diff,
            file_contents={
                "src/payments/service.py": (
                    "def charge(request):\n"
                    "    if request.retry_count > 3:\n"
                    "        raise PaymentRetryLimitExceeded(\n"
                    '            "retry limit reached",\n'
                    "        )\n"
                ),
            },
        ),
        detectors=(detect_test_shape_risks,),
        context_max_chars=2_000,
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "test_shape.missing_behavior_coverage"
    assert finding.pillar == "test_integrity"
    assert finding.status == "warning"
    assert 50 <= finding.score < 80
    assert 0.4 <= finding.confidence < 0.7
    assert finding.evidence_refs == (
        "file:src/payments/service.py",
        "diff:src/payments/service.py",
    )
    assert finding.decision_source == "deterministic"
    assert finding.calibration_reason == (
        "behavior_change_without_test_evidence_low_confidence"
    )
    assert finding.tags == ("detector:test_shape", LOW_CONFIDENCE_TAG)
    assert result.context_envelope.items[0].detector_id == "test_shape"


def test_test_shape_detector_flags_disabled_tests_with_redacted_excerpt() -> None:
    """Keeps disabled test evidence useful without leaking raw secret-shaped text."""
    test_diff = (
        "diff --git a/tests/test_payments.py b/tests/test_payments.py\n"
        "@@ retry limit tests @@\n"
        '+@pytest.mark.skip(reason="flaky api_key=sk_live_1234567890abcdef")\n'
        "+def test_charge_retry_limit_is_enforced():\n"
        "+    assert charge(request) == expected_receipt\n"
    )
    result = run_static_detectors(
        _evidence_pack(
            changed_files=(_changed_file("tests/test_payments.py", test_diff),),
            diff=test_diff,
            file_contents={
                "tests/test_payments.py": (
                    '@pytest.mark.skip(reason="flaky api_key=sk_live_1234567890abcdef")\n'
                    "def test_charge_retry_limit_is_enforced():\n"
                    "    assert charge(request) == expected_receipt\n"
                ),
            },
        ),
        detectors=(detect_test_shape_risks,),
        context_max_chars=2_000,
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "test_shape.disabled_test"
    assert finding.pillar == "test_integrity"
    assert finding.status == "warning"
    assert finding.score >= 60
    assert finding.confidence >= 0.6
    assert finding.evidence_refs == (
        "file:tests/test_payments.py",
        "diff:tests/test_payments.py",
    )
    assert finding.decision_source == "deterministic"
    assert finding.calibration_reason == "disabled_test_reduces_test_integrity"
    assert finding.tags == ("detector:test_shape", "test:disabled")
    assert finding.redacted_excerpts

    rendered_excerpts = "\n".join(
        excerpt.text for excerpt in finding.redacted_excerpts
    )
    assert len(rendered_excerpts) <= MAX_REDACTED_EXCERPT_LENGTH
    assert "pytest.mark.skip" in rendered_excerpts
    assert "api_key=<REDACTED_SECRET>" in rendered_excerpts
    assert "sk_live_1234567890abcdef" not in rendered_excerpts
    assert "diff --git" not in rendered_excerpts
    assert result.context_envelope.items[0].redacted_excerpts == (rendered_excerpts,)


def test_test_shape_detector_ignores_style_only_source_changes() -> None:
    """Prevents missing-test noise for comments, formatting, and docs-only changes."""
    style_only_diff = (
        "diff --git a/src/payments/service.py b/src/payments/service.py\n"
        "@@ module comments @@\n"
        "+# Keep retry helpers close to payment behavior.\n"
        '+"""Payment retry helpers."""\n'
    )

    findings = detect_test_shape_risks(
        _evidence_pack(
            changed_files=(
                _changed_file("src/payments/service.py", style_only_diff),
            ),
            diff=style_only_diff,
            file_contents={
                "src/payments/service.py": (
                    "# Keep retry helpers close to payment behavior.\n"
                    '"""Payment retry helpers."""\n'
                ),
            },
        ),
    )

    assert findings == ()
