from pr_radar.contracts import (
    ContextBudget,
    ContextEnvelope,
    ContextEnvelopeItem,
    RADAR_PILLARS,
)


def _envelope(*items: ContextEnvelopeItem) -> ContextEnvelope:
    return ContextEnvelope(
        context_grade="review_grade",
        budget=ContextBudget(max_chars=4_000, used_chars=0, is_over_budget=False),
        items=items,
    )


def _item(
    *,
    finding_id: str,
    pillar: str,
    status: str,
    score: int,
    confidence: float = 0.8,
    tags: tuple[str, ...] = (),
    calibration_reason: str | None = None,
) -> ContextEnvelopeItem:
    return ContextEnvelopeItem(
        finding_id=finding_id,
        detector_id=finding_id.split(".", maxsplit=1)[0],
        pillar=pillar,
        title=f"Finding {finding_id}",
        status=status,
        score=score,
        confidence=confidence,
        evidence_refs=(f"file:{finding_id}.py",),
        calibration_reason=calibration_reason,
        tags=tags,
    )


def test_local_scorer_requests_changes_for_blocking_or_score_threshold() -> None:
    """Locks ADR-022: blocked findings or score >= 85 request changes."""
    from pr_radar.review.local_scorer import DecisionModelAdapter, KevLocalScorer

    assert isinstance(KevLocalScorer(), DecisionModelAdapter)

    decision = KevLocalScorer().score(
        _envelope(
            _item(
                finding_id="migration.destructive.drop_table",
                pillar="deployment_downtime",
                status="critical",
                score=90,
                calibration_reason="destructive_migration_detected",
            ),
        ),
    )

    assert decision.recommendation == "REQUEST_CHANGES"
    assert decision.overall_score == 90
    assert decision.decision_source == "kev_local_scorer"
    assert "SCORE_THRESHOLD_REACHED" in decision.primary_reason_codes
    assert decision.finding_decisions[0].recommendation == "REQUEST_CHANGES"
    assert decision.evaluated_pillars["deployment_downtime"].status == "blocked"


def test_local_scorer_accepts_internal_policy_threshold_injection() -> None:
    """Keeps score tuning internal without exposing CLI/env configuration."""
    from pr_radar.review.local_scorer import KevLocalScorer, LocalScorerPolicy

    decision = KevLocalScorer(
        policy=LocalScorerPolicy(request_changes_score_threshold=75),
    ).score(
        _envelope(
            _item(
                finding_id="dependency.added.package",
                pillar="security_supply_chain",
                status="warning",
                score=76,
            ),
        ),
    )

    assert decision.recommendation == "REQUEST_CHANGES"
    assert "SCORE_THRESHOLD_REACHED" in decision.primary_reason_codes


def test_local_scorer_requires_human_review_for_high_risk_core_pillars() -> None:
    """Locks ADR-022 high-risk deployment/security aggregation."""
    from pr_radar.review.local_scorer import KevLocalScorer

    decision = KevLocalScorer().score(
        _envelope(
            _item(
                finding_id="dependency.added.package",
                pillar="security_supply_chain",
                status="high",
                score=82,
                calibration_reason="dependency_added_manifest_requires_review",
            ),
            _item(
                finding_id="migration.destructive.alter_column",
                pillar="deployment_downtime",
                status="high",
                score=78,
                calibration_reason="destructive_migration_detected",
            ),
        ),
    )

    assert decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert decision.overall_score == 82
    assert decision.primary_reason_codes == (
        "HIGH_RISK_DEPLOYMENT_DOWNTIME",
        "HIGH_RISK_SECURITY_SUPPLY_CHAIN",
    )
    assert decision.evaluated_pillars["security_supply_chain"].status == "high_risk"
    assert decision.evaluated_pillars["deployment_downtime"].status == "high_risk"


def test_local_scorer_prefers_reason_based_high_risk_before_pillar_fallback() -> None:
    """Locks ADR-024 reason-first high-risk classification."""
    from pr_radar.review.local_scorer import KevLocalScorer, LocalScorerPolicy

    decision = KevLocalScorer(
        policy=LocalScorerPolicy(
            high_risk_calibration_reasons={
                "destructive_migration_detected": "HIGH_RISK_DEPLOYMENT_DOWNTIME",
            },
        ),
    ).score(
        _envelope(
            _item(
                finding_id="migration.destructive.drop_table",
                pillar="experimental_future_pillar",
                status="info",
                score=62,
                calibration_reason="destructive_migration_detected",
            ),
        ),
    )

    assert decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert decision.primary_reason_codes == ("HIGH_RISK_DEPLOYMENT_DOWNTIME",)
    assert decision.evaluated_pillars["experimental_future_pillar"].status == (
        "high_risk"
    )


def test_local_scorer_approves_with_caution_for_warnings_or_low_confidence() -> None:
    """Keeps ambiguous findings visible without over-blocking developers."""
    from pr_radar.review.local_scorer import KevLocalScorer

    decision = KevLocalScorer().score(
        _envelope(
            _item(
                finding_id="test_shape.disabled_test",
                pillar="test_integrity",
                status="warning",
                score=66,
                tags=("detector:test_shape",),
            ),
            _item(
                finding_id="dependency.added.ambiguous",
                pillar="security_supply_chain",
                status="info",
                score=45,
                confidence=0.42,
                tags=("low_confidence",),
            ),
        ),
    )

    assert decision.recommendation == "APPROVE_WITH_CAUTION"
    assert decision.overall_score == 66
    assert decision.primary_reason_codes == (
        "LOW_CONFIDENCE_FINDING_PRESENT",
        "WARNING_FINDING_PRESENT",
    )
    assert decision.finding_decisions[0].recommendation == "APPROVE_WITH_CAUTION"
    assert decision.finding_decisions[1].recommendation == "APPROVE_WITH_CAUTION"


def test_local_scorer_approves_empty_context_and_marks_pillars_not_evaluated() -> None:
    """Prevents absent detectors from being silently implied safe."""
    from pr_radar.review.local_scorer import KevLocalScorer

    decision = KevLocalScorer().score(_envelope())

    assert decision.recommendation == "APPROVE"
    assert decision.overall_score == 0
    assert decision.overall_confidence == 1.0
    assert decision.primary_reason_codes == ("NO_MATERIAL_FINDINGS",)
    assert decision.finding_decisions == ()
    assert tuple(decision.evaluated_pillars) == tuple(
        pillar.key for pillar in RADAR_PILLARS
    )
    assert all(
        pillar_decision.status == "not_evaluated"
        for pillar_decision in decision.evaluated_pillars.values()
    )
