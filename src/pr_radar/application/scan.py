import os
from collections.abc import Callable, Mapping

from pr_radar.adapters.github.urllib_http import urllib_http_get
from pr_radar.application.context import ContextEnvelope
from pr_radar.contracts import AiSignalFinding, DecisionStatus, Finding, Report
from pr_radar.detectors.ai_signal import detect_ai_signals
from pr_radar.detectors import get_default_static_detectors
from pr_radar.detectors.static_risk import run_static_detectors
from pr_radar.github_adapter import (
    GitHubEvidenceFetchError,
    GitHubHttpResponse,
    fetch_pr_evidence,
)
from pr_radar.pull_requests.identity import PrUrlParseError, parse_pr_url


_STATIC_CONTEXT_MAX_CHARS = 12_000
_LOW_CONFIDENCE_TAG = "low confidence"


class ScanError(ValueError):
    """Raised when a local PR scan cannot produce a report safely."""


def scan_pr(
    pr_url: str,
    *,
    fetch_evidence: bool = False,
    env: Mapping[str, str] | None = None,
    http_get: Callable[..., GitHubHttpResponse] = urllib_http_get,
) -> Report:
    try:
        pr_input = parse_pr_url(pr_url)
    except PrUrlParseError as error:
        raise ScanError(str(error)) from error

    if not fetch_evidence:
        return Report(
            overall_status="safe",
            pr_input=pr_input,
            ai_signal_summary="No AI-generation evidence collected yet.",
            evaluation_metadata={
                "context_grade": "parser_only",
                "context_envelope": "unavailable",
            },
        )

    try:
        evidence_pack = fetch_pr_evidence(
            pr_input,
            env=os.environ if env is None else env,
            http_get=http_get,
            include_file_contents=True,
        )
    except GitHubEvidenceFetchError as error:
        raise ScanError(
            f"Unable to fetch PR evidence: {error.failure.reason}",
        ) from error

    ai_signal_findings = detect_ai_signals(evidence_pack)
    static_risk_result = run_static_detectors(
        evidence_pack,
        detectors=get_default_static_detectors(),
        context_max_chars=_STATIC_CONTEXT_MAX_CHARS,
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
        evaluation_metadata=_context_metadata(
            static_risk_result.context_envelope,
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
        if _LOW_CONFIDENCE_TAG in finding.tags
    )


def _context_metadata(context_envelope: ContextEnvelope) -> dict[str, str]:
    return {
        "context_grade": context_envelope.context_grade,
        "context_envelope": "available",
        "context_finding_count": str(len(context_envelope.items)),
        "context_budget_max_chars": str(context_envelope.budget.max_chars),
        "context_budget_used_chars": str(context_envelope.budget.used_chars),
        "context_budget_is_over_budget": str(context_envelope.budget.is_over_budget),
    }
