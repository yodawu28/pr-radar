"""GitHub provider adapter public API."""

from pr_radar.adapters.github.auth import (
    API_BASE_URL_OVERRIDE_ENV,
    DEFAULT_GITHUB_COM_TOKEN_ENV,
    DEFAULT_GITHUB_SELF_HOSTED_TOKEN_ENV,
    TOKEN_ENV_OVERRIDE_ENV,
    DefaultGitHubAuthEnvVar,
    GitHubApiPlan,
    GitHubAuthResolutionError,
    resolve_github_api_plan,
)
from pr_radar.adapters.github.fetcher import (
    GitHubEvidenceFetchError,
    fetch_pr_evidence,
)
from pr_radar.adapters.github.http import (
    GitHubHttpResponse,
    GitHubHttpTimeout,
)

__all__ = (
    "API_BASE_URL_OVERRIDE_ENV",
    "DEFAULT_GITHUB_COM_TOKEN_ENV",
    "DEFAULT_GITHUB_SELF_HOSTED_TOKEN_ENV",
    "TOKEN_ENV_OVERRIDE_ENV",
    "DefaultGitHubAuthEnvVar",
    "GitHubApiPlan",
    "GitHubAuthResolutionError",
    "GitHubEvidenceFetchError",
    "GitHubHttpResponse",
    "GitHubHttpTimeout",
    "fetch_pr_evidence",
    "resolve_github_api_plan",
)
