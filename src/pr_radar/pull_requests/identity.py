from urllib.parse import urlparse, urlunparse

from pr_radar.contracts import PrDeployment, PrInput


class PrUrlParseError(ValueError):
    """Raised when a pull request URL cannot be parsed safely."""


def parse_pr_url(url: str) -> PrInput:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""

    if scheme not in {"http", "https"} or not host:
        raise PrUrlParseError("Invalid PR URL: expected an absolute URL.")
    if parsed.username or parsed.password:
        raise PrUrlParseError("Invalid PR URL: credentials are not allowed.")

    netloc = host
    try:
        port = parsed.port
    except ValueError as error:
        raise PrUrlParseError("Invalid PR URL: invalid port.") from error
    if port:
        netloc = f"{host}:{port}"

    path_parts = [part for part in parsed.path.split("/") if part]
    if _looks_like_unsupported_provider(path_parts):
        raise PrUrlParseError("Invalid PR URL: unsupported provider.")

    if len(path_parts) < 3 or path_parts[2] != "pull":
        raise PrUrlParseError("Invalid PR URL: expected a pull request path.")

    if len(path_parts) < 4 or not path_parts[3].isdigit():
        raise PrUrlParseError("Invalid PR URL: expected a pull request number.")

    owner, repository_name, _, pull_request_number = path_parts[:4]
    normalized_url = urlunparse(
        (
            scheme,
            netloc,
            f"/{owner}/{repository_name}/pull/{pull_request_number}",
            "",
            "",
            "",
        ),
    )

    return PrInput(
        provider="github",
        deployment=_deployment_for_host(host),
        repository=f"{owner}/{repository_name}",
        pull_request_number=int(pull_request_number),
        url=normalized_url,
    )


def _looks_like_unsupported_provider(path_parts: list[str]) -> bool:
    return "merge_requests" in path_parts


def _deployment_for_host(host: str) -> PrDeployment:
    if host == "github.com":
        return "github_com"
    return "github_self_hosted"
