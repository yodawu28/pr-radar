import pytest

from pr_radar.application.context import (
    ContextBudget,
    ContextEnvelope,
    ContextEnvelopeItem,
)


def _safe_envelope(*, excerpt: str = '+ requests = "<REDACTED_SECRET>"') -> ContextEnvelope:
    return ContextEnvelope(
        context_grade="review_grade",
        budget=ContextBudget(max_chars=1_200, used_chars=180, is_over_budget=False),
        items=(
            ContextEnvelopeItem(
                finding_id="dependency.added.requests",
                detector_id="dependency",
                pillar="security_supply_chain",
                title="New dependency requires supply-chain review",
                status="warning",
                score=68,
                confidence=0.74,
                evidence_refs=("file:pyproject.toml", "diff:pyproject.toml"),
                calibration_reason=(
                    "dependency_added_manifest_requires_supply_chain_review"
                ),
                redacted_excerpts=(excerpt,),
                tags=("detector:dependency",),
            ),
        ),
    )


def test_decision_context_guard_accepts_report_safe_context() -> None:
    """Locks the safe path before a scorer consumes bounded context."""
    from pr_radar.review.context_guard import validate_decision_context

    result = validate_decision_context(_safe_envelope())

    assert result.is_safe is True
    assert result.reason_codes == ()


@pytest.mark.parametrize(
    ("payload", "reason_code"),
    (
        (
            "diff --git a/src/service.py b/src/service.py\n"
            "--- a/src/service.py\n"
            "+++ b/src/service.py",
            "raw_diff_marker",
        ),
        (
            "@@ -10,7 +10,8 @@ def handle_request():\n"
            "-    old_call()\n"
            "+    new_call()",
            "raw_diff_hunk",
        ),
        (
            "def handle_request(user):\n"
            "    private_token = user.api_token\n"
            "    return private_token",
            "raw_source_payload",
        ),
        (
            "api_key=sk_live_1234567890abcdef",
            "credential_like_token",
        ),
    ),
)
def test_decision_context_guard_rejects_raw_context_before_scoring(
    payload: str,
    reason_code: str,
) -> None:
    """Prevents the Sprint 4 scorer from seeing raw diff/source/secrets."""
    from pr_radar.review.context_guard import (
        DecisionContextRejected,
        validate_decision_context,
    )

    with pytest.raises(DecisionContextRejected) as error:
        validate_decision_context(_safe_envelope(excerpt=payload))

    assert reason_code in error.value.reason_codes


def test_decision_context_guard_reports_reason_codes_without_raw_payload() -> None:
    """Keeps guard errors content-free for audit logs and fallback decisions."""
    from pr_radar.review.context_guard import (
        DecisionContextRejected,
        validate_decision_context,
    )

    raw_payload = (
        "diff --git a/app.py b/app.py\n"
        "@@ -1,1 +1,2 @@\n"
        "api_key=sk_live_1234567890abcdef"
    )

    with pytest.raises(DecisionContextRejected) as error:
        validate_decision_context(_safe_envelope(excerpt=raw_payload))

    assert error.value.reason_codes == (
        "credential_like_token",
        "raw_diff_hunk",
        "raw_diff_marker",
    )
    assert "diff --git" not in str(error.value)
    assert "sk_live_1234567890abcdef" not in str(error.value)
