from importlib import import_module

import pytest
from pydantic import ValidationError


def _contracts_module():
    try:
        return import_module("pr_radar.contracts")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.contracts module: {error}")


def _decision_contracts():
    contracts = _contracts_module()
    missing = tuple(
        name
        for name in (
            "RiskDecision",
            "FindingDecision",
            "PillarDecision",
            "DecisionRecommendation",
            "PillarDecisionStatus",
        )
        if not hasattr(contracts, name)
    )

    assert missing == (), (
        "expected Sprint 4 decision contract names exported by "
        f"pr_radar.contracts: {missing}"
    )
    return (
        contracts,
        contracts.RiskDecision,
        contracts.FindingDecision,
        contracts.PillarDecision,
    )


def test_risk_decision_contract_records_overall_recommendation() -> None:
    """Catches prose-only decision output without bounded Sprint 4 metadata."""
    (
        _contracts,
        RiskDecision,
        FindingDecision,
        PillarDecision,
    ) = _decision_contracts()

    finding_decision = FindingDecision(
        finding_id="dependency.added.requests",
        recommendation="APPROVE_WITH_CAUTION",
        score=68,
        confidence=0.74,
        reason_codes=("WARNING_FINDING_PRESENT",),
        evidence_refs=("file:pyproject.toml",),
        decision_source="kev_local_scorer",
    )
    pillar_decision = PillarDecision(
        pillar="security_supply_chain",
        status="warning",
        score=68,
        confidence=0.74,
        reason_codes=("WARNING_FINDING_PRESENT",),
        evaluated_finding_ids=("dependency.added.requests",),
    )
    decision = RiskDecision(
        recommendation="APPROVE_WITH_CAUTION",
        overall_score=68,
        overall_confidence=0.74,
        decision_source="kev_local_scorer",
        primary_reason_codes=("WARNING_FINDING_PRESENT",),
        finding_decisions=(finding_decision,),
        evaluated_pillars={"security_supply_chain": pillar_decision},
        context_envelope_ref="context-envelope:sha256:abc123",
    )

    assert decision.recommendation == "APPROVE_WITH_CAUTION"
    assert decision.overall_score == 68
    assert decision.overall_confidence == 0.74
    assert decision.decision_source == "kev_local_scorer"
    assert decision.primary_reason_codes == ("WARNING_FINDING_PRESENT",)
    assert decision.finding_decisions == (finding_decision,)
    assert decision.evaluated_pillars["security_supply_chain"] is pillar_decision
    assert decision.context_envelope_ref == "context-envelope:sha256:abc123"


def test_decision_recommendation_vocabulary_excludes_reject() -> None:
    """Keeps PR Radar advisory and developer-in-control in Phase 1."""
    (
        _contracts,
        RiskDecision,
        _FindingDecision,
        _PillarDecision,
    ) = _decision_contracts()

    for recommendation in (
        "APPROVE",
        "APPROVE_WITH_CAUTION",
        "NEEDS_HUMAN_REVIEW",
        "REQUEST_CHANGES",
    ):
        decision = RiskDecision(
            recommendation=recommendation,
            overall_score=0,
            overall_confidence=1.0,
            decision_source="kev_local_scorer",
        )
        assert decision.recommendation == recommendation

    with pytest.raises(ValidationError):
        RiskDecision(
            recommendation="REJECT",
            overall_score=100,
            overall_confidence=1.0,
            decision_source="kev_local_scorer",
        )


def test_pillar_decision_status_vocabulary_is_fixed() -> None:
    """Catches hidden or implied-safe pillars when detectors are absent."""
    (
        _contracts,
        _RiskDecision,
        _FindingDecision,
        PillarDecision,
    ) = _decision_contracts()

    for status in (
        "not_evaluated",
        "no_findings",
        "warning",
        "high_risk",
        "blocked",
        "unavailable",
    ):
        decision = PillarDecision(
            pillar="deployment_downtime",
            status=status,
            score=0,
            confidence=1.0,
        )
        assert decision.status == status

    with pytest.raises(ValidationError):
        PillarDecision(
            pillar="deployment_downtime",
            status="safe",
            score=0,
            confidence=1.0,
        )


def test_decision_reason_code_vocabulary_is_public_contract() -> None:
    """Catches scorer reason-code strings drifting from evaluation fixtures."""
    contracts = _contracts_module()

    assert hasattr(contracts, "DecisionReasonCode")
    assert tuple(contracts.DECISION_REASON_CODES) == (
        "SCORE_THRESHOLD_REACHED",
        "BLOCKED_FINDING_PRESENT",
        "HIGH_RISK_DEPLOYMENT_DOWNTIME",
        "HIGH_RISK_SECURITY_SUPPLY_CHAIN",
        "LOW_CONFIDENCE_FINDING_PRESENT",
        "WARNING_FINDING_PRESENT",
        "NO_MATERIAL_FINDINGS",
        "DECISION_SCORER_UNAVAILABLE",
        "DECISION_CONTEXT_MISSING",
        "DECISION_CONTEXT_BUDGET_EXCEEDED",
    )


def test_decision_contracts_are_strict_and_immutable() -> None:
    """Prevents decision contracts from becoming loose metadata bags."""
    (
        _contracts,
        RiskDecision,
        FindingDecision,
        PillarDecision,
    ) = _decision_contracts()

    with pytest.raises(ValidationError):
        FindingDecision(
            finding_id="migration.destructive.drop_table",
            recommendation="REQUEST_CHANGES",
            score=95,
            confidence=0.9,
            reason_codes=("BLOCKED_FINDING_PRESENT",),
            evidence_refs=("diff:db/migrate/001.sql",),
            decision_source="kev_local_scorer",
            raw_diff="diff --git a/db/migrate/001.sql b/db/migrate/001.sql",
        )

    decision = RiskDecision(
        recommendation="NEEDS_HUMAN_REVIEW",
        overall_score=85,
        overall_confidence=0.81,
        decision_source="kev_local_scorer",
        finding_decisions=[
            FindingDecision(
                finding_id="migration.destructive.drop_table",
                recommendation="REQUEST_CHANGES",
                score=95,
                confidence=0.9,
                reason_codes=["BLOCKED_FINDING_PRESENT"],
                evidence_refs=["diff:db/migrate/001.sql"],
                decision_source="kev_local_scorer",
            ),
        ],
        evaluated_pillars={
            "deployment_downtime": PillarDecision(
                pillar="deployment_downtime",
                status="blocked",
                score=95,
                confidence=0.9,
                reason_codes=["BLOCKED_FINDING_PRESENT"],
                evaluated_finding_ids=["migration.destructive.drop_table"],
            ),
        },
    )

    assert isinstance(decision.finding_decisions, tuple)
    assert decision.finding_decisions[0].reason_codes == ("BLOCKED_FINDING_PRESENT",)
    assert decision.finding_decisions[0].evidence_refs == ("diff:db/migrate/001.sql",)
    assert decision.evaluated_pillars["deployment_downtime"].reason_codes == (
        "BLOCKED_FINDING_PRESENT",
    )

    with pytest.raises(ValidationError):
        RiskDecision(
            recommendation="NEEDS_HUMAN_REVIEW",
            overall_score=101,
            overall_confidence=0.81,
            decision_source="kev_local_scorer",
        )

    with pytest.raises(ValidationError):
        RiskDecision(
            recommendation="NEEDS_HUMAN_REVIEW",
            overall_score=85,
            overall_confidence=1.01,
            decision_source="kev_local_scorer",
        )
