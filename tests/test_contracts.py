import warnings
from importlib import import_module

import pytest
from pydantic import ValidationError


def _contracts_module():
    try:
        return import_module("pr_radar.contracts")
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.contracts module: {error}")


def test_contract_facade_exports_stable_public_names() -> None:
    """Catches accidental facade churn when contract internals are split."""
    contracts = _contracts_module()

    assert contracts.__all__ == (
        "REPORT_SCHEMA_VERSION",
        "CONTEXT_ENVELOPE_SCHEMA_VERSION",
        "BlastRadiusSummary",
        "BlastRadiusDependent",
        "BlastRadiusBudget",
        "ContextEnvelope",
        "ContextEnvelopeItem",
        "ContextBudget",
        "ContextGrade",
        "RADAR_PILLARS",
        "RadarPillarDefinition",
        "RadarPillarKey",
        "PrInput",
        "PrDeployment",
        "PrMetadata",
        "CommitMetadata",
        "ChangedFileMetadata",
        "ChangedFileStatus",
        "GitHubChangedFileStatus",
        "RawEvidence",
        "EvidenceReference",
        "EvidenceReferenceKind",
        "RedactedExcerpt",
        "FetchFailure",
        "FetchFailureReason",
        "AiSignalFinding",
        "AiSignalCalibrationReason",
        "AiSignalType",
        "AiSignalStrength",
        "PrEvidencePack",
        "Decision",
        "DecisionReasonCode",
        "DECISION_REASON_CODES",
        "RiskDecision",
        "FindingDecision",
        "PillarDecision",
        "Finding",
        "LOW_CONFIDENCE_TAG",
        "Report",
        "DecisionStatus",
        "DecisionRecommendation",
        "PillarDecisionStatus",
        "FindingStatus",
        "DecisionSource",
    )


def test_contract_facade_reexports_domain_modules() -> None:
    """Catches flattening contract internals back into a monolithic module."""
    contracts = _contracts_module()

    inputs = import_module("pr_radar.contracts.inputs")
    evidence = import_module("pr_radar.contracts.evidence")
    decisions = import_module("pr_radar.contracts.decisions")
    findings = import_module("pr_radar.contracts.findings")
    reports = import_module("pr_radar.contracts.reports")
    blast_radius = import_module("pr_radar.contracts.blast_radius")
    context = import_module("pr_radar.contracts.context")
    radar = import_module("pr_radar.contracts.radar")

    assert contracts.BlastRadiusSummary is blast_radius.BlastRadiusSummary
    assert contracts.BlastRadiusDependent is blast_radius.BlastRadiusDependent
    assert contracts.BlastRadiusBudget is blast_radius.BlastRadiusBudget
    assert contracts.ContextEnvelope is context.ContextEnvelope
    assert contracts.ContextEnvelopeItem is context.ContextEnvelopeItem
    assert contracts.ContextBudget is context.ContextBudget
    assert contracts.RADAR_PILLARS is radar.RADAR_PILLARS
    assert contracts.RadarPillarDefinition is radar.RadarPillarDefinition
    assert contracts.PrInput is inputs.PrInput
    assert contracts.PrDeployment is inputs.PrDeployment
    assert contracts.PrMetadata is evidence.PrMetadata
    assert contracts.CommitMetadata is evidence.CommitMetadata
    assert contracts.ChangedFileMetadata is evidence.ChangedFileMetadata
    assert contracts.ChangedFileStatus is evidence.ChangedFileStatus
    assert contracts.GitHubChangedFileStatus is evidence.GitHubChangedFileStatus
    assert contracts.RawEvidence is evidence.RawEvidence
    assert contracts.EvidenceReference is evidence.EvidenceReference
    assert contracts.EvidenceReferenceKind is evidence.EvidenceReferenceKind
    assert contracts.RedactedExcerpt is evidence.RedactedExcerpt
    assert contracts.FetchFailure is evidence.FetchFailure
    assert contracts.FetchFailureReason is evidence.FetchFailureReason
    assert contracts.AiSignalFinding is evidence.AiSignalFinding
    assert contracts.AiSignalCalibrationReason is evidence.AiSignalCalibrationReason
    assert contracts.AiSignalType is evidence.AiSignalType
    assert contracts.AiSignalStrength is evidence.AiSignalStrength
    assert contracts.PrEvidencePack is evidence.PrEvidencePack
    assert contracts.Decision is decisions.Decision
    assert contracts.DECISION_REASON_CODES is decisions.DECISION_REASON_CODES
    assert contracts.RiskDecision is decisions.RiskDecision
    assert contracts.FindingDecision is decisions.FindingDecision
    assert contracts.PillarDecision is decisions.PillarDecision
    assert contracts.Finding is findings.Finding
    assert contracts.Report is reports.Report
    assert contracts.REPORT_SCHEMA_VERSION is reports.REPORT_SCHEMA_VERSION


def test_radar_pillars_are_fixed_contract_vocabulary() -> None:
    """Catches renderer/scorer drift from the executive radar shape."""
    contracts = _contracts_module()

    assert tuple(pillar.key for pillar in contracts.RADAR_PILLARS) == (
        "security_supply_chain",
        "deployment_downtime",
        "blast_radius_downstream",
        "performance_footprint",
        "anti_bloat_dry",
        "test_integrity",
        "rollback_feature_flags",
    )


def test_pr_input_requires_github_identity_and_deployment() -> None:
    """Catches missing strict validation for PR URL identity contracts."""
    contracts = _contracts_module()

    pr_input = contracts.PrInput(
        provider="github",
        deployment="github_com",
        repository="example/repo",
        pull_request_number=17,
        url="https://github.com/example/repo/pull/17",
    )

    assert pr_input.provider == "github"
    assert pr_input.deployment == "github_com"
    assert pr_input.repository == "example/repo"
    assert pr_input.pull_request_number == 17
    assert pr_input.url == "https://github.com/example/repo/pull/17"

    with pytest.raises(ValidationError):
        contracts.PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
            raw_diff="private diff must not be persisted",
        )

    with pytest.raises(ValidationError):
        contracts.PrInput(
            provider="github",
            deployment="gitlab_self_hosted",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        )


def test_finding_contract_bounds_scores_and_preserves_evidence_refs() -> None:
    """Catches unbounded risk scores or missing evidence references."""
    contracts = _contracts_module()

    finding = contracts.Finding(
        id="finding-001",
        pillar="security_supply_chain",
        title="New dependency requires review",
        status="warning",
        score=70,
        confidence=0.82,
        evidence_refs=["pyproject.toml:8"],
        decision_source="deterministic",
        calibration_reason="dependency_added_manifest_requires_supply_chain_review",
        tags=[contracts.LOW_CONFIDENCE_TAG],
    )

    assert finding.status == "warning"
    assert finding.score == 70
    assert finding.confidence == 0.82
    assert finding.evidence_refs == ("pyproject.toml:8",)
    assert finding.calibration_reason == (
        "dependency_added_manifest_requires_supply_chain_review"
    )
    assert finding.tags == (contracts.LOW_CONFIDENCE_TAG,)

    with pytest.raises(ValidationError):
        contracts.Finding(
            id="finding-002",
            pillar="security_supply_chain",
            title="Score too high",
            status="warning",
            score=101,
            confidence=0.5,
            evidence_refs=["pyproject.toml:8"],
            decision_source="deterministic",
            tags=[],
        )

    with pytest.raises(ValidationError):
        contracts.Finding(
            id="finding-003",
            pillar="security_supply_chain",
            title="Invalid status",
            status="nitpick",
            score=10,
            confidence=0.5,
            evidence_refs=["pyproject.toml:8"],
            decision_source="deterministic",
            tags=[],
        )


def test_decision_contract_records_status_score_confidence_and_source() -> None:
    """Catches prose-only decisions that lose bounded model metadata."""
    contracts = _contracts_module()

    decision = contracts.Decision(
        status="needs_attention",
        score=60,
        confidence=0.7,
        evidence_refs=["src/service.py:42"],
        decision_source="kev_local",
    )

    assert decision.status == "needs_attention"
    assert decision.score == 60
    assert decision.confidence == 0.7
    assert decision.evidence_refs == ("src/service.py:42",)
    assert decision.decision_source == "kev_local"

    with pytest.raises(ValidationError):
        contracts.Decision(
            status="needs_attention",
            score=60,
            confidence=1.5,
            evidence_refs=["src/service.py:42"],
            decision_source="kev_local",
        )


def test_report_contract_groups_findings_without_mutable_defaults() -> None:
    """Catches report contracts that share mutable finding collections."""
    contracts = _contracts_module()
    pr_input = contracts.PrInput(
        provider="github",
        deployment="github_com",
        repository="example/repo",
        pull_request_number=17,
        url="https://github.com/example/repo/pull/17",
    )
    finding = contracts.Finding(
        id="finding-001",
        pillar="test_integrity",
        title="Mock hides database behavior",
        status="warning",
        score=55,
        confidence=0.64,
        evidence_refs=["tests/test_export.py:12"],
        decision_source="deterministic",
        tags=[contracts.LOW_CONFIDENCE_TAG],
    )

    report = contracts.Report(
        overall_status="needs_attention",
        pr_input=pr_input,
        ai_signal_summary="No explicit agent signature found.",
        findings=[finding],
        low_confidence_findings=[finding],
        evaluation_metadata={"ground_truth": "not_configured"},
    )
    empty_report = contracts.Report(
        overall_status="safe",
        pr_input=pr_input,
        ai_signal_summary="No evidence collected yet.",
    )

    assert report.schema_version == "pr-radar.report.v1"
    assert report.findings == (finding,)
    assert report.low_confidence_findings == (finding,)
    assert report.evaluation_metadata == {"ground_truth": "not_configured"}
    assert empty_report.findings == ()
    assert empty_report.low_confidence_findings == ()

    with pytest.raises(TypeError):
        report.evaluation_metadata["raw_url"] = "private audit data"

    with pytest.raises(TypeError):
        empty_report.evaluation_metadata["raw_url"] = "private audit data"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dumped_report = report.model_dump()

    assert dumped_report["schema_version"] == "pr-radar.report.v1"
    assert dumped_report["evaluation_metadata"] == {"ground_truth": "not_configured"}
    assert isinstance(dumped_report["evaluation_metadata"], dict)
    assert not caught

    with pytest.raises(ValidationError):
        contracts.Report(
            overall_status="auto_approve",
            pr_input=pr_input,
            ai_signal_summary="Invalid status should fail.",
        )

    with pytest.raises(ValidationError):
        contracts.Report(
            schema_version="pr-radar.report.v2",
            overall_status="safe",
            pr_input=pr_input,
            ai_signal_summary="Unknown schema versions should fail.",
        )
