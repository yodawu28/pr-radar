from collections.abc import Mapping

from pydantic import Field

from pr_radar.contracts.base import StrictContract


class GitHubHttpTimeout(TimeoutError):
    """Raised by an injected GitHub HTTP adapter on timeout."""


class GitHubHttpResponse(StrictContract):
    status_code: int
    body: object
    headers: Mapping[str, str] = Field(default_factory=dict)
