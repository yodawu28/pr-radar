from pr_radar.contracts import Finding, Report
from pr_radar.privacy.redaction import redact_text


RADAR_PILLARS: tuple[tuple[str, str], ...] = (
    ("security_supply_chain", "Security & Supply Chain"),
    ("deployment_downtime", "Deployment & Downtime"),
    ("blast_radius_downstream", "Blast Radius & Downstream"),
    ("performance_footprint", "Performance & Footprint"),
    ("anti_bloat_dry", "Anti-Bloat & DRY"),
    ("test_integrity", "Test Integrity & Edge Cases"),
    ("rollback_feature_flags", "Rollback & Feature Flags"),
)


def render_text_report(report: Report) -> str:
    lines = [
        "PR Radar Local Report",
        f"Schema Version: {report.schema_version}",
        f"Overall Status: {report.overall_status}",
        f"PR: {report.pr_input.repository}#{report.pr_input.pull_request_number}",
        f"URL: {report.pr_input.url}",
        f"AI Signal: {redact_text(report.ai_signal_summary, limit=False)}",
        "",
        "Radar",
    ]

    findings_by_pillar = _group_findings_by_pillar(report.findings)
    known_pillars = {pillar_key for pillar_key, _ in RADAR_PILLARS}
    for pillar_key, pillar_label in RADAR_PILLARS:
        pillar_findings = findings_by_pillar.get(pillar_key, ())
        if not pillar_findings:
            lines.append(f"{pillar_label}: No findings yet.")
            continue

        lines.append(f"{pillar_label}:")
        lines.extend(_format_finding(finding) for finding in pillar_findings)

    other_findings = tuple(
        finding
        for finding in report.findings
        if finding.pillar not in known_pillars
    )
    if other_findings:
        lines.append("Other Findings:")
        lines.extend(_format_finding(finding) for finding in other_findings)

    lines.append("")
    lines.append("Low Confidence Findings")
    if not report.low_confidence_findings:
        lines.append("None.")
    else:
        lines.extend(
            _format_finding(finding)
            for finding in report.low_confidence_findings
        )

    return "\n".join(lines)


def _group_findings_by_pillar(
    findings: tuple[Finding, ...],
) -> dict[str, tuple[Finding, ...]]:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.pillar, []).append(finding)
    return {
        pillar: tuple(pillar_findings)
        for pillar, pillar_findings in grouped.items()
    }


def _format_finding(finding: Finding) -> str:
    tags = f" tags={','.join(finding.tags)}" if finding.tags else ""
    evidence = ", ".join(finding.evidence_refs)
    excerpts = _format_excerpts(finding)
    return (
        f"- {finding.id} [{finding.status}] pillar={finding.pillar} "
        f"score={finding.score} "
        f"confidence={finding.confidence:.2f} source={finding.decision_source}"
        f"{tags}: {finding.title} evidence={evidence}{excerpts}"
    )


def _format_excerpts(finding: Finding) -> str:
    if not finding.redacted_excerpts:
        return ""
    excerpts = " | ".join(
        redact_text(excerpt.text)
        for excerpt in finding.redacted_excerpts
    )
    return f" excerpt={excerpts}"
