from collections.abc import Mapping

from pr_radar.adapters.github.http import GitHubHttpResponse
from pr_radar.contracts import (
    ChangedFileMetadata,
    PrEvidencePack,
    PrInput,
    PrMetadata,
    RawEvidence,
)
from pr_radar.scan import scan_pr


def _unused_http_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> GitHubHttpResponse:
    raise AssertionError(f"http_get should not be called in scan fixture: {url}")


def _changed_file(path: str, diff: str) -> ChangedFileMetadata:
    return ChangedFileMetadata(
        path=path,
        status="modified",
        additions=diff.count("\n+"),
        deletions=diff.count("\n-"),
    )


def test_review_grade_scan_attaches_risk_decision(monkeypatch) -> None:
    """Catches scan flow stopping at findings without a Sprint 4 decision."""
    dependency_diff = (
        "diff --git a/pyproject.toml b/pyproject.toml\n"
        "@@ [project] dependencies @@\n"
        '+    "requests>=2.32",\n'
    )

    def fake_fetch_pr_evidence(
        pr_input: PrInput,
        *,
        env: Mapping[str, str],
        http_get,
        include_file_contents: bool = False,
    ) -> PrEvidencePack:
        return PrEvidencePack(
            pr_input=pr_input,
            pr_metadata=PrMetadata(
                title="Add dependency",
                body="",
                author_login="alice",
                head_ref="feature/dependency",
                base_ref="main",
            ),
            changed_files=(_changed_file("pyproject.toml", dependency_diff),),
            raw_evidence=RawEvidence(
                diff=dependency_diff,
                file_contents={
                    "pyproject.toml": (
                        "[project]\n"
                        "dependencies = [\n"
                        '    "requests>=2.32",\n'
                        "]\n"
                    ),
                },
            ),
        )

    monkeypatch.setattr(
        "pr_radar.application.scan.fetch_pr_evidence",
        fake_fetch_pr_evidence,
    )

    report = scan_pr(
        "https://github.com/example/repo/pull/17",
        fetch_evidence=True,
        env={"GITHUB_TOKEN": "github_unit_secret_value"},
        http_get=_unused_http_get,
    )

    assert report.overall_status == "needs_attention"
    assert report.risk_decision is not None
    assert report.risk_decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert report.risk_decision.decision_source == "kev_local_scorer"
    assert report.risk_decision.evaluated_pillars["security_supply_chain"].status == (
        "high_risk"
    )
    assert report.risk_decision.evaluated_pillars["test_integrity"].status == (
        "not_evaluated"
    )
    assert report.risk_decision.finding_decisions[0].finding_id == (
        "dependency.added.pyproject"
    )

    serialized_report = str(report.model_dump(mode="json"))
    assert "diff --git" not in serialized_report
    assert "PRIVATE_RAW_SOURCE" not in serialized_report


def test_parser_only_scan_reports_unavailable_decision_context() -> None:
    """Parser-only PR URL scans must not imply the decision layer approved."""
    report = scan_pr(
        "https://github.com/example/repo/pull/17",
        fetch_evidence=False,
    )

    assert report.overall_status == "needs_attention"
    assert report.risk_decision is not None
    assert report.risk_decision.recommendation == "NEEDS_HUMAN_REVIEW"
    assert report.risk_decision.decision_source == "unavailable"
    assert report.risk_decision.primary_reason_codes == (
        "DECISION_CONTEXT_MISSING",
    )
