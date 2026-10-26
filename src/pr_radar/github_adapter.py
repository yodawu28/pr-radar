"""Backward-compatible GitHub adapter facade."""

from pr_radar.adapters.github import (
    API_BASE_URL_OVERRIDE_ENV,
    DEFAULT_GITHUB_COM_TOKEN_ENV,
    DEFAULT_GITHUB_SELF_HOSTED_TOKEN_ENV,
    TOKEN_ENV_OVERRIDE_ENV,
    DefaultGitHubAuthEnvVar,
    GitHubApiPlan,
    GitHubAuthResolutionError,
    GitHubEvidenceFetchError,
    GitHubHttpResponse,
    GitHubHttpTimeout,
    fetch_pr_evidence,
    resolve_github_api_plan,
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
