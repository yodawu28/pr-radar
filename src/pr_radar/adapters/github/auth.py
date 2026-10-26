from collections.abc import Mapping
from typing import Literal, TypeAlias
from urllib.parse import urlparse

from pr_radar.contracts import FetchFailure, PrInput
from pr_radar.contracts.base import StrictContract


DEFAULT_GITHUB_COM_TOKEN_ENV = "GITHUB_TOKEN"
DEFAULT_GITHUB_SELF_HOSTED_TOKEN_ENV = "GHE_TOKEN"
API_BASE_URL_OVERRIDE_ENV = "PR_RADAR_GITHUB_API_BASE_URL"
TOKEN_ENV_OVERRIDE_ENV = "PR_RADAR_GITHUB_TOKEN_ENV"

DefaultGitHubAuthEnvVar: TypeAlias = Literal["GITHUB_TOKEN", "GHE_TOKEN"]


class GitHubApiPlan(StrictContract):
    api_base_url: str
    auth_env_var: str
    token: str


class GitHubAuthResolutionError(ValueError):
    """Raised when GitHub API auth cannot be resolved safely."""

    def __init__(self, failure: FetchFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


def resolve_github_api_plan(
    pr_input: PrInput,
    *,
    env: Mapping[str, str],
) -> GitHubApiPlan:
    api_base_url, auth_env_var = _deployment_api_base_and_auth_env(
        pr_input,
        env=env,
    )
    token = env.get(auth_env_var)
    if not token or not token.strip():
        raise GitHubAuthResolutionError(
            FetchFailure(
                reason="missing_token",
                message=_missing_token_message(auth_env_var),
            ),
        )

    return GitHubApiPlan(
        api_base_url=api_base_url,
        auth_env_var=auth_env_var,
        token=token,
    )


def _deployment_api_base_and_auth_env(
    pr_input: PrInput,
    *,
    env: Mapping[str, str],
) -> tuple[str, str]:
    if pr_input.provider != "github":
        raise GitHubAuthResolutionError(
            FetchFailure(
                reason="unsupported_provider",
                message="Unsupported provider for GitHub API planning.",
            ),
        )

    auth_env_var = env.get(TOKEN_ENV_OVERRIDE_ENV)
    if pr_input.deployment == "github_com":
        return (
            _api_base_url_from_env(env) or "https://api.github.com",
            auth_env_var or DEFAULT_GITHUB_COM_TOKEN_ENV,
        )

    if pr_input.deployment == "github_self_hosted":
        api_base_url = _api_base_url_from_env(env)
        if api_base_url is None:
            parsed = urlparse(pr_input.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise GitHubAuthResolutionError(
                    FetchFailure(
                        reason="unsupported_deployment",
                        message="Unsupported self-hosted GitHub URL.",
                    ),
                )
            api_base_url = f"{parsed.scheme}://{parsed.netloc}/api/v3"
        return api_base_url, auth_env_var or DEFAULT_GITHUB_SELF_HOSTED_TOKEN_ENV

    raise GitHubAuthResolutionError(
        FetchFailure(
            reason="unsupported_deployment",
            message="Unsupported GitHub deployment.",
        ),
    )


def _api_base_url_from_env(env: Mapping[str, str]) -> str | None:
    api_base_url = env.get(API_BASE_URL_OVERRIDE_ENV)
    if api_base_url is None or not api_base_url.strip():
        return None

    parsed = urlparse(api_base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise GitHubAuthResolutionError(
            FetchFailure(
                reason="unsupported_deployment",
                message="Invalid PR_RADAR_GITHUB_API_BASE_URL.",
            ),
        )
    return api_base_url.rstrip("/")


def _missing_token_message(auth_env_var: str) -> str:
    return f"Missing {auth_env_var} for GitHub API planning."
