import os
from collections.abc import Callable, Mapping
from pathlib import Path

from pr_radar.adapters.github.urllib_http import urllib_http_get
from pr_radar.application.blast_radius import trace_blast_radius
from pr_radar.application.scan_metadata import (
    ContextGrade as ScanContextGrade,
    ScanEvaluationMetadata,
)
from pr_radar.application.scan_policy import DEFAULT_SCAN_POLICY, ScanPolicy
from pr_radar.contracts import (
    AiSignalFinding,
    BlastRadiusBudget,
    BlastRadiusSummary,
    ContextEnvelope,
    DecisionStatus,
    Finding,
    LOW_CONFIDENCE_TAG,
    PrEvidencePack,
    Report,
)
from pr_radar.detectors.ai_signal import detect_ai_signals
from pr_radar.detectors import get_default_static_detectors
from pr_radar.detectors.static_risk import run_static_detectors
from pr_radar.github_adapter import (
    GitHubEvidenceFetchError,
    GitHubHttpResponse,
    fetch_pr_evidence,
)
from pr_radar.pull_requests.identity import PrUrlParseError, parse_pr_url
from pr_radar.review import evaluate_risk_decision


class ScanError(ValueError):
    """Raised when a local PR scan cannot produce a report safely."""


def scan_pr(
    pr_url: str,
    *,
    fetch_evidence: bool = False,
    local_workspace_path: str | Path | None = None,
    scan_policy: ScanPolicy = DEFAULT_SCAN_POLICY,
    env: Mapping[str, str] | None = None,
    http_get: Callable[..., GitHubHttpResponse] = urllib_http_get,
) -> Report:
    try:
        pr_input = parse_pr_url(pr_url)
    except PrUrlParseError as error:
        raise ScanError(str(error)) from error

    if not fetch_evidence:
        return Report(
            overall_status="needs_attention",
            pr_input=pr_input,
            ai_signal_summary="No AI-generation evidence collected yet.",
            risk_decision=evaluate_risk_decision(None),
            evaluation_metadata=_parser_only_metadata(),
        )

    try:
        evidence_pack = fetch_pr_evidence(
            pr_input,
            env=os.environ if env is None else env,
            http_get=http_get,
            include_file_contents=scan_policy.include_file_contents,
        )
    except GitHubEvidenceFetchError as error:
        raise ScanError(
            f"Unable to fetch PR evidence: {error.failure.reason}",
        ) from error

    ai_signal_findings = detect_ai_signals(evidence_pack)
    blast_radius_summary = _blast_radius_summary(
        evidence_pack=evidence_pack,
        local_workspace_path=local_workspace_path,
        scan_policy=scan_policy,
    )
    static_risk_result = run_static_detectors(
        evidence_pack,
        detectors=get_default_static_detectors(),
        context_max_chars=scan_policy.static_context_max_chars,
        blast_radius_summary=blast_radius_summary,
    )
    return Report(
        overall_status=_overall_status(
            findings=static_risk_result.findings,
            ai_signal_findings=ai_signal_findings,
        ),
        pr_input=pr_input,
        ai_signal_summary=_ai_signal_summary(ai_signal_findings),
        findings=static_risk_result.findings,
        low_confidence_findings=_low_confidence_findings(
            static_risk_result.findings,
        ),
        risk_decision=evaluate_risk_decision(static_risk_result.context_envelope),
        evaluation_metadata=_context_metadata(
            static_risk_result.context_envelope,
            blast_radius_summary=blast_radius_summary,
            local_workspace_path=local_workspace_path,
        ),
    )


def _ai_signal_summary(
    ai_signal_findings: tuple[AiSignalFinding, ...],
) -> str:
    if not ai_signal_findings:
        return "No AI-generation evidence detected in fetched PR evidence."

    lines = [
        f"{len(ai_signal_findings)} signal(s) detected: "
        f"{', '.join(finding.signal_type for finding in ai_signal_findings)}",
    ]
    for finding in ai_signal_findings:
        lines.append(
            f"- {finding.signal_type} [{finding.status}] "
            f"score={finding.score} confidence={finding.confidence:.2f} "
            f"source={finding.decision_source} "
            f"reason={finding.calibration_reason}",
        )
        if finding.tags:
            lines.append(f"  Tags: {', '.join(finding.tags)}")
        for evidence_ref in finding.evidence_refs:
            lines.append(f"  Evidence: {evidence_ref.ref}")
        for excerpt in finding.redacted_excerpts:
            lines.append(f"  Excerpt: {excerpt.text}")
    return "\n".join(lines)


def _overall_status(
    *,
    findings: tuple[Finding, ...],
    ai_signal_findings: tuple[AiSignalFinding, ...],
) -> DecisionStatus:
    if any(finding.status == "critical" for finding in findings):
        return "blocker"
    if any(finding.status == "high" for finding in findings):
        return "high_risk"
    if findings or ai_signal_findings:
        return "needs_attention"
    return "safe"


def _low_confidence_findings(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    return tuple(
        finding
        for finding in findings
        if LOW_CONFIDENCE_TAG in finding.tags
    )


def _parser_only_metadata() -> dict[str, str]:
    return ScanEvaluationMetadata(
        context_grade="parser_only",
        context_envelope="unavailable",
        context_finding_count=0,
        context_budget_max_chars=0,
        context_budget_used_chars=0,
        context_budget_is_over_budget=False,
        blast_radius_context_grade="parser_only",
        blast_radius_availability="unavailable",
        blast_radius_reason_code="parser_only",
        blast_radius_dependent_count=0,
        blast_radius_truncated=False,
    ).to_report_metadata()


def _blast_radius_summary(
    *,
    evidence_pack: PrEvidencePack,
    local_workspace_path: str | Path | None,
    scan_policy: ScanPolicy,
) -> BlastRadiusSummary:
    changed_paths = tuple(file.path for file in evidence_pack.changed_files)
    if local_workspace_path is None:
        return BlastRadiusSummary(
            availability="unavailable",
            reason_code="requires_local_workspace",
            changed_paths=changed_paths,
            direct_dependents=(),
            dependent_count=0,
            budget=BlastRadiusBudget(
                max_dependents=scan_policy.blast_radius_max_dependents,
                emitted_dependents=0,
                omitted_dependents=0,
            ),
            truncated=False,
        )

    return trace_blast_radius(
        workspace_path=local_workspace_path,
        changed_paths=changed_paths,
        max_dependents=scan_policy.blast_radius_max_dependents,
    )


def _context_metadata(
    context_envelope: ContextEnvelope,
    *,
    blast_radius_summary: BlastRadiusSummary,
    local_workspace_path: str | Path | None,
) -> dict[str, str]:
    blast_radius_context_grade = _blast_radius_context_grade(
        blast_radius_summary=blast_radius_summary,
        local_workspace_path=local_workspace_path,
    )
    return ScanEvaluationMetadata(
        context_grade=context_envelope.context_grade,
        context_envelope="available",
        context_finding_count=len(context_envelope.items),
        context_budget_max_chars=context_envelope.budget.max_chars,
        context_budget_used_chars=context_envelope.budget.used_chars,
        context_budget_is_over_budget=context_envelope.budget.is_over_budget,
        blast_radius_context_grade=blast_radius_context_grade,
        blast_radius_availability=blast_radius_summary.availability,
        blast_radius_reason_code=blast_radius_summary.reason_code,
        blast_radius_dependent_count=blast_radius_summary.dependent_count,
        blast_radius_truncated=blast_radius_summary.truncated,
        blast_radius_changed_paths=blast_radius_summary.changed_paths,
        blast_radius_direct_dependents=tuple(
            dependent.dependent_path
            for dependent in blast_radius_summary.direct_dependents
        ),
    ).to_report_metadata()


def _blast_radius_context_grade(
    *,
    blast_radius_summary: BlastRadiusSummary,
    local_workspace_path: str | Path | None,
) -> ScanContextGrade:
    if local_workspace_path is None:
        return "unavailable"
    if blast_radius_summary.availability in {"available", "partial"}:
        return "review_grade"
    return "unavailable"
