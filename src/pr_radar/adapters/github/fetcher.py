from collections.abc import Callable, Mapping

from pr_radar.adapters.github.auth import (
    GitHubAuthResolutionError,
    resolve_github_api_plan,
)
from pr_radar.adapters.github.http import GitHubHttpResponse, GitHubHttpTimeout
from pr_radar.adapters.github.mapper import (
    changed_file,
    commit,
    evidence_refs,
    mapping_body,
    mapping_body_from_object,
    pr_metadata,
    sequence_body,
    text_body,
)
from pr_radar.adapters.github.security import is_trusted_raw_file_url
from pr_radar.contracts import (
    FetchFailure,
    PrEvidencePack,
    PrInput,
    RawEvidence,
)


class GitHubEvidenceFetchError(ValueError):
    """Raised when GitHub PR evidence cannot be fetched safely."""

    def __init__(self, failure: FetchFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


def fetch_pr_evidence(
    pr_input: PrInput,
    *,
    env: Mapping[str, str],
    http_get: Callable[..., GitHubHttpResponse],
    include_file_contents: bool = False,
) -> PrEvidencePack:
    try:
        api_plan = resolve_github_api_plan(pr_input, env=env)
    except GitHubAuthResolutionError as error:
        raise GitHubEvidenceFetchError(error.failure) from error

    api_pr_url = (
        f"{api_plan.api_base_url}/repos/{pr_input.repository}"
        f"/pulls/{pr_input.pull_request_number}"
    )
    json_headers = _headers(api_plan.token)

    pr_body = mapping_body(
        _fetch_response(api_pr_url, headers=json_headers, http_get=http_get),
    )
    commits_body = sequence_body(
        _fetch_response(
            f"{api_pr_url}/commits",
            headers=json_headers,
            http_get=http_get,
        ),
    )
    files_body = sequence_body(
        _fetch_response(
            f"{api_pr_url}/files",
            headers=json_headers,
            http_get=http_get,
        ),
    )
    diff = text_body(
        _fetch_response(
            api_pr_url,
            headers=_headers(api_plan.token, accept="application/vnd.github.v3.diff"),
            http_get=http_get,
        ),
    )

    changed_files = tuple(changed_file(file_body) for file_body in files_body)
    file_contents: dict[str, str] = {}
    if include_file_contents:
        for file_body in files_body:
            file = mapping_body_from_object(file_body)
            raw_url = file.get("raw_url")
            filename = file.get("filename")
            if isinstance(raw_url, str) and isinstance(filename, str):
                file_contents[filename] = text_body(
                    _fetch_response(
                        _trusted_raw_file_url(raw_url, pr_input),
                        headers=json_headers,
                        http_get=http_get,
                    ),
                )

    return PrEvidencePack(
        pr_input=pr_input,
        pr_metadata=pr_metadata(pr_body),
        commits=tuple(commit(commit_body) for commit_body in commits_body),
        changed_files=changed_files,
        raw_evidence=RawEvidence(diff=diff, file_contents=file_contents),
        evidence_refs=evidence_refs(changed_files),
    )


def _headers(
    token: str,
    *,
    accept: str = "application/vnd.github+json",
) -> dict[str, str]:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {token}",
    }


def _fetch_response(
    url: str,
    *,
    headers: Mapping[str, str],
    http_get: Callable[..., GitHubHttpResponse],
) -> GitHubHttpResponse:
    try:
        response = http_get(url, headers=headers)
    except GitHubHttpTimeout as error:
        raise GitHubEvidenceFetchError(
            FetchFailure(
                reason="timeout",
                message="Timed out while fetching GitHub PR evidence.",
            ),
        ) from error

    if response.status_code != 200:
        raise GitHubEvidenceFetchError(_http_failure(response.status_code))
    return response


def _trusted_raw_file_url(
    raw_url: str,
    pr_input: PrInput,
) -> str:
    if not is_trusted_raw_file_url(raw_url, pr_input):
        raise GitHubEvidenceFetchError(
            FetchFailure(
                reason="unsupported_deployment",
                message="Unsupported GitHub raw file URL.",
            ),
        )
    return raw_url


def _http_failure(status_code: int) -> FetchFailure:
    if status_code == 401:
        return FetchFailure(
            reason="unauthorized",
            message="GitHub API authentication failed.",
        )
    if status_code == 403:
        return FetchFailure(
            reason="forbidden",
            message="GitHub API access was forbidden.",
        )
    if status_code == 404:
        return FetchFailure(
            reason="not_found",
            message="GitHub pull request evidence was not found.",
        )
    if status_code == 429:
        return FetchFailure(
            reason="rate_limited",
            message="GitHub API rate limit was reached.",
        )
    return FetchFailure(
        reason="forbidden",
        message="GitHub API request failed.",
    )
