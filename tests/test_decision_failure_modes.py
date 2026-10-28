from typing import NoReturn

from pr_radar.contracts import (
    ContextBudget,
    ContextEnvelope,
    ContextEnvelopeItem,
    RADAR_PILLARS,
)


def _item(
    *,
    finding_id: str = "dependency.added.package",
    pillar: str = "security_supply_chain",
    status: str = "warning",
    score: int = 70,
) -> ContextEnvelopeItem:
    return ContextEnvelopeItem(
        finding_id=finding_id,
        detector_id=finding_id.split(".", maxsplit=1)[0],
        pillar=pillar,
        title="New dependency requires review",
        status=status,
        score=score,
        confidence=0.74,
        evidence_refs=("file:pyproject.toml",),
        calibration_reason="dependency_added_manifest_requires_review",
    )


def _envelope(
    *items: ContextEnvelopeItem,
    is_over_budget: bool = False,
) -> ContextEnvelope:
    return ContextEnvelope(
        context_grade="review_grade",
        budget=ContextBudget(
            max_chars=100,
            used_chars=180 if is_over_budget else 80,
            is_over_budget=is_over_budget,
        ),
        items=items,
    )


class _ExplodingScorer:
    def score(self, context_envelope: ContextEnvelope) -> NoReturn:
        raise RuntimeError("scorer backend unavailable")


class _RecordingScorer:
    was_called = False

    def score(self, context_envelope: ContextEnvelope) -> NoReturn:
        self.was_called = True
        raise AssertionError("raw context reached scorer")


def test_decision_runner_degrades_scorer_exception_to_human_review() -> None:
    """Keeps static finding evidence visible when the decision scorer crashes."""
    from pr_radar.review.decision_runner import evaluate_risk_decision

    decision = evaluate_risk_decision(
        _envelope(_item()),
        scorer=_ExplodingScorer(),
    )

    assert decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert decision.decision_source == "unavailable"
    assert decision.primary_reason_codes == ("DECISION_SCORER_UNAVAILABLE",)
    assert decision.finding_decisions[0].finding_id == "dependency.added.package"
    assert decision.finding_decisions[0].evidence_refs == ("file:pyproject.toml",)
    assert decision.evaluated_pillars["security_supply_chain"].status == "unavailable"


def test_decision_runner_degrades_missing_context_to_human_review() -> None:
    """Prevents absent decision context from being reported as safe."""
    from pr_radar.review.decision_runner import evaluate_risk_decision

    decision = evaluate_risk_decision(None)

    assert decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert decision.decision_source == "unavailable"
    assert decision.primary_reason_codes == ("DECISION_CONTEXT_MISSING",)
    assert decision.finding_decisions == ()
    assert tuple(decision.evaluated_pillars) == tuple(
        pillar.key for pillar in RADAR_PILLARS
    )
    assert all(
        pillar.status == "unavailable"
        for pillar in decision.evaluated_pillars.values()
    )


def test_decision_runner_degrades_over_budget_context_to_human_review() -> None:
    """Fails closed when bounded context exceeded its deterministic budget."""
    from pr_radar.review.decision_runner import evaluate_risk_decision

    decision = evaluate_risk_decision(
        _envelope(_item(), is_over_budget=True),
    )

    assert decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert decision.decision_source == "unavailable"
    assert decision.primary_reason_codes == ("DECISION_CONTEXT_BUDGET_EXCEEDED",)
    assert decision.finding_decisions[0].finding_id == "dependency.added.package"
    assert decision.evaluated_pillars["security_supply_chain"].status == "unavailable"


def test_decision_runner_rejects_raw_context_before_scorer_execution() -> None:
    """Keeps raw diff/source markers out of the decision scorer."""
    from pr_radar.review.context_guard import DecisionContextRejected
    from pr_radar.review.decision_runner import evaluate_risk_decision

    scorer = _RecordingScorer()
    raw_context_item = _item(
        finding_id="dependency.added.raw_context",
    ).model_copy(
        update={
            "redacted_excerpts": (
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "@@ -1,1 +1,2 @@\n"
                "+api_key=sk_live_1234567890abcdef",
            ),
        },
    )

    try:
        evaluate_risk_decision(
            _envelope(raw_context_item),
            scorer=scorer,
        )
    except DecisionContextRejected as error:
        assert "raw_diff_marker" in error.reason_codes
        assert "credential_like_token" in error.reason_codes
    else:
        raise AssertionError("raw decision context was not rejected")

    assert scorer.was_called is False
