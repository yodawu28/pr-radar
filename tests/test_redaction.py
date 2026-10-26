from pr_radar.contracts import EvidenceReference
from pr_radar.redaction import MAX_REDACTED_EXCERPT_LENGTH, redact_excerpt


def _diff_ref() -> EvidenceReference:
    return EvidenceReference(kind="diff", ref="diff:src/review.py")


def test_redact_excerpt_masks_auth_headers_tokens_and_api_keys() -> None:
    """Catches report excerpts that leak credentials while describing a risk."""
    raw_excerpt = (
        "+ Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456\n"
        "+ Authorization: Basic dXNlcjpwYXNz\n"
        "+ api_key=sk_live_1234567890abcdef\n"
        "+ service_token: line_internal_secret_value"
    )

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert excerpt.evidence_ref == _diff_ref()
    assert "Authorization: Bearer <REDACTED_TOKEN>" in excerpt.text
    assert "Authorization: Basic <REDACTED_TOKEN>" in excerpt.text
    assert "api_key=<REDACTED_SECRET>" in excerpt.text
    assert "service_token: <REDACTED_SECRET>" in excerpt.text
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in excerpt.text
    assert "dXNlcjpwYXNz" not in excerpt.text
    assert "sk_live_1234567890abcdef" not in excerpt.text
    assert "line_internal_secret_value" not in excerpt.text


def test_redact_excerpt_masks_url_userinfo_credentials() -> None:
    """Catches embedded URL credentials leaking through report-safe snippets."""
    raw_excerpt = (
        "+ clone_url=https://deploy-user:super-secret@ghe.internal/team/repo.git"
    )

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert "https://<REDACTED_CREDENTIALS>@ghe.internal/team/repo.git" in excerpt.text
    assert "deploy-user" not in excerpt.text
    assert "super-secret" not in excerpt.text


def test_redact_excerpt_masks_emails_and_sensitive_internal_urls() -> None:
    """Catches private identity and internal system URLs in report excerpts."""
    raw_excerpt = (
        "+ owner=alice.smith@corp.example\n"
        "+ trace=https://ghe.corp.yahoo.co.jp/paypaygw/e2e-stg/pull/499\n"
        "+ see https://git.linecorp.com/arkdevelopers/code-review-agent/pull/59"
    )

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert "<REDACTED_EMAIL>" in excerpt.text
    assert "alice.smith@corp.example" not in excerpt.text
    assert "https://<REDACTED_INTERNAL_URL>" in excerpt.text
    assert "paypaygw/e2e-stg" not in excerpt.text
    assert "arkdevelopers/code-review-agent" not in excerpt.text


def test_redact_excerpt_masks_credentialed_sensitive_internal_urls() -> None:
    """Catches URL-userinfo redaction leaving sensitive internal repo paths."""
    raw_excerpt = (
        "+ remote=https://deploy-user:secret@git.linecorp.com/team/private-repo.git"
    )

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert "https://<REDACTED_INTERNAL_URL>" in excerpt.text
    assert "deploy-user" not in excerpt.text
    assert "secret" not in excerpt.text
    assert "git.linecorp.com" not in excerpt.text
    assert "team/private-repo" not in excerpt.text


def test_redact_excerpt_preserves_verification_context() -> None:
    """Catches redaction that erases the surrounding review evidence."""
    raw_excerpt = (
        "+ Generated with Claude Code\n"
        "+ api_key=sk_live_1234567890abcdef\n"
        "+ called from src/review.py"
    )

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert "Generated with Claude Code" in excerpt.text
    assert "called from src/review.py" in excerpt.text
    assert excerpt.evidence_ref.ref == "diff:src/review.py"


def test_redact_excerpt_limits_report_safe_snippet_length() -> None:
    """Catches long raw evidence bodies flowing into report-safe excerpts."""
    raw_excerpt = "+ generated change\n" + ("safe context " * 80)

    excerpt = redact_excerpt(evidence_ref=_diff_ref(), text=raw_excerpt)

    assert len(excerpt.text) <= MAX_REDACTED_EXCERPT_LENGTH
    assert excerpt.text.endswith("...")
    assert "generated change" in excerpt.text
