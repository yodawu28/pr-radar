import pytest
from typer.testing import CliRunner

from pr_radar.cli import app
from pr_radar.contracts import PrInput
from pr_radar.github_adapter import (
    GitHubEvidenceFetchError,
    GitHubHttpResponse,
    GitHubHttpTimeout,
    fetch_pr_evidence,
)


API_BASE_URL = "https://git.linecorp.com/api/v3"
PROXY_API_BASE_URL = "https://ghe-proxy.internal/api/v3"
REPOSITORY = "arkdevelopers/code-review-agent"
PULL_REQUEST_NUMBER = 59
PR_API_URL = f"{API_BASE_URL}/repos/{REPOSITORY}/pulls/{PULL_REQUEST_NUMBER}"
PROXY_PR_API_URL = (
    f"{PROXY_API_BASE_URL}/repos/{REPOSITORY}/pulls/{PULL_REQUEST_NUMBER}"
)
COMMITS_API_URL = f"{PR_API_URL}/commits"
FILES_API_URL = f"{PR_API_URL}/files"
DIFF_ACCEPT = "application/vnd.github.v3.diff"


class FakeGitHubHttp:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, *, headers):
        self.calls.append({"url": url, "headers": dict(headers)})
        route_key = (url, headers.get("Accept"))
        result = self.routes.get(route_key, self.routes.get(url))
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise AssertionError(f"unexpected HTTP GET {url}")
        return result


def _response(status_code, body, headers=None):
    return GitHubHttpResponse(
        status_code=status_code,
        body=body,
        headers=headers or {},
    )


def _pr_input() -> PrInput:
    return PrInput(
        provider="github",
        deployment="github_self_hosted",
        repository=REPOSITORY,
        pull_request_number=PULL_REQUEST_NUMBER,
        url=f"https://git.linecorp.com/{REPOSITORY}/pull/{PULL_REQUEST_NUMBER}",
    )


def test_fetch_pr_evidence_collects_metadata_commits_files_diff_and_file_content():
    """Catches fetchers that stop at metadata and never collect raw local evidence."""
    token = "ghe_unit_secret_value"
    raw_url = "https://git.linecorp.com/raw/src/review.py"
    fake_http = FakeGitHubHttp(
        {
            PR_API_URL: _response(
                200,
                {
                    "title": "Add generated review helper",
                    "body": "Generated with Claude Code",
                    "user": {"login": "alice"},
                    "head": {"ref": "cursor/review-helper"},
                    "base": {"ref": "main"},
                    "labels": [{"name": "agent-pr"}],
                },
            ),
            COMMITS_API_URL: _response(
                200,
                [
                    {
                        "sha": "abc1234",
                        "author": {"login": "devin[bot]"},
                        "committer": {"login": "github-actions[bot]"},
                        "commit": {"message": "Generate review helper"},
                    },
                ],
            ),
            FILES_API_URL: _response(
                200,
                [
                    {
                        "filename": "src/review.py",
                        "status": "modified",
                        "additions": 12,
                        "deletions": 3,
                        "raw_url": raw_url,
                    },
                ],
            ),
            (PR_API_URL, DIFF_ACCEPT): _response(
                200,
                "diff --git a/src/review.py b/src/review.py\n+TOKEN=secret",
            ),
            raw_url: _response(200, "TOKEN=secret"),
        },
    )

    evidence_pack = fetch_pr_evidence(
        _pr_input(),
        env={"GHE_TOKEN": token},
        http_get=fake_http.get,
        include_file_contents=True,
    )

    assert evidence_pack.pr_metadata.title == "Add generated review helper"
    assert evidence_pack.pr_metadata.author_login == "alice"
    assert evidence_pack.pr_metadata.labels == ("agent-pr",)
    assert evidence_pack.commits[0].sha == "abc1234"
    assert evidence_pack.commits[0].author_login == "devin[bot]"
    assert evidence_pack.changed_files[0].path == "src/review.py"
    assert evidence_pack.raw_evidence.diff.startswith("diff --git")
    assert evidence_pack.raw_evidence.file_contents == {
        "src/review.py": "TOKEN=secret",
    }
    assert any(
        call["headers"].get("Authorization") == f"Bearer {token}"
        for call in fake_http.calls
    )


def test_fetch_pr_evidence_missing_token_fails_before_http_call():
    """Catches fetchers that call network before fail-closed auth validation."""
    fake_http = FakeGitHubHttp({})

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            _pr_input(),
            env={},
            http_get=fake_http.get,
        )

    assert caught.value.failure.reason == "missing_token"
    assert fake_http.calls == []


@pytest.mark.parametrize(
    ("status_code", "expected_reason"),
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not_found"),
        (429, "rate_limited"),
    ],
)
def test_fetch_pr_evidence_maps_http_failures_to_typed_fetch_errors(
    status_code,
    expected_reason,
):
    """Catches raw provider errors leaking through the fetch seam."""
    token = "ghe_unit_secret_value"
    fake_http = FakeGitHubHttp(
        {
            PR_API_URL: _response(
                status_code,
                {"message": f"provider message with {token}"},
            ),
        },
    )

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            _pr_input(),
            env={"GHE_TOKEN": token},
            http_get=fake_http.get,
        )

    serialized_failure = caught.value.failure.model_dump_json()
    assert caught.value.failure.reason == expected_reason
    assert token not in str(caught.value)
    assert token not in repr(caught.value)
    assert token not in serialized_failure


def test_fetch_pr_evidence_maps_timeout_to_typed_fetch_error_without_token_leak():
    """Catches timeout exceptions surfacing raw transport detail."""
    token = "ghe_unit_secret_value"
    fake_http = FakeGitHubHttp(
        {
            PR_API_URL: GitHubHttpTimeout(
                f"connect timed out while using {token}",
            ),
        },
    )

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            _pr_input(),
            env={"GHE_TOKEN": token},
            http_get=fake_http.get,
        )

    serialized_failure = caught.value.failure.model_dump_json()
    assert caught.value.failure.reason == "timeout"
    assert token not in str(caught.value)
    assert token not in repr(caught.value)
    assert token not in serialized_failure


def test_fetch_pr_evidence_rejects_cross_host_raw_file_url_before_http_call():
    """Catches token exfiltration through provider-supplied raw file URLs."""
    token = "ghe_unit_secret_value"
    attacker_raw_url = "https://attacker.example/raw/src/review.py"
    fake_http = FakeGitHubHttp(
        {
            PR_API_URL: _response(
                200,
                {
                    "title": "Add generated review helper",
                    "body": "Generated with Claude Code",
                    "user": {"login": "alice"},
                    "head": {"ref": "cursor/review-helper"},
                    "base": {"ref": "main"},
                    "labels": [],
                },
            ),
            COMMITS_API_URL: _response(200, []),
            FILES_API_URL: _response(
                200,
                [
                    {
                        "filename": "src/review.py",
                        "status": "modified",
                        "additions": 12,
                        "deletions": 3,
                        "raw_url": attacker_raw_url,
                    },
                ],
            ),
            (PR_API_URL, DIFF_ACCEPT): _response(200, "diff --git"),
        },
    )

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            _pr_input(),
            env={"GHE_TOKEN": token},
            http_get=fake_http.get,
            include_file_contents=True,
        )

    serialized_failure = caught.value.failure.model_dump_json()
    assert caught.value.failure.reason == "unsupported_deployment"
    assert token not in str(caught.value)
    assert token not in serialized_failure
    assert not any(call["url"] == attacker_raw_url for call in fake_http.calls)


def test_fetch_pr_evidence_rejects_self_hosted_api_proxy_raw_file_url():
    """Catches API proxy hosts becoming implicit raw file content hosts."""
    token = "ghe_unit_secret_value"
    proxy_raw_url = "https://ghe-proxy.internal/raw/src/review.py"
    fake_http = FakeGitHubHttp(
        {
            PROXY_PR_API_URL: _response(
                200,
                {
                    "title": "Add generated review helper",
                    "body": "Generated with Claude Code",
                    "user": {"login": "alice"},
                    "head": {"ref": "cursor/review-helper"},
                    "base": {"ref": "main"},
                    "labels": [],
                },
            ),
            f"{PROXY_PR_API_URL}/commits": _response(200, []),
            f"{PROXY_PR_API_URL}/files": _response(
                200,
                [
                    {
                        "filename": "src/review.py",
                        "status": "modified",
                        "additions": 12,
                        "deletions": 3,
                        "raw_url": proxy_raw_url,
                    },
                ],
            ),
            (PROXY_PR_API_URL, DIFF_ACCEPT): _response(200, "diff --git"),
            proxy_raw_url: _response(200, "TOKEN=secret"),
        },
    )

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            _pr_input(),
            env={
                "GHE_TOKEN": token,
                "PR_RADAR_GITHUB_API_BASE_URL": PROXY_API_BASE_URL,
            },
            http_get=fake_http.get,
            include_file_contents=True,
        )

    serialized_failure = caught.value.failure.model_dump_json()
    assert caught.value.failure.reason == "unsupported_deployment"
    assert token not in str(caught.value)
    assert token not in serialized_failure
    assert not any(call["url"] == proxy_raw_url for call in fake_http.calls)


def test_fetch_pr_evidence_invalid_self_hosted_url_fails_before_http_call():
    """Catches unsupported self-hosted URL inputs reaching the HTTP layer."""
    unsupported_input = PrInput(
        provider="github",
        deployment="github_self_hosted",
        repository=REPOSITORY,
        pull_request_number=PULL_REQUEST_NUMBER,
        url=f"not-a-url/{REPOSITORY}/pull/59",
    )
    fake_http = FakeGitHubHttp({})

    with pytest.raises(GitHubEvidenceFetchError) as caught:
        fetch_pr_evidence(
            unsupported_input,
            env={"GHE_TOKEN": "ghe_unit_secret_value"},
            http_get=fake_http.get,
        )

    assert caught.value.failure.reason == "unsupported_deployment"
    assert fake_http.calls == []


def test_scan_baseline_path_still_renders_without_fetch_access():
    """Catches Sprint 2 fetch work breaking the Sprint 1 no-fetch baseline path."""
    result = CliRunner().invoke(
        app,
        ["scan", "https://git.example.internal/team/repo/pull/42"],
    )

    assert result.exit_code == 0
    assert "PR Radar Local Report" in result.output
    assert "PR: team/repo#42" in result.output
    assert "No AI-generation evidence collected yet." in result.output
