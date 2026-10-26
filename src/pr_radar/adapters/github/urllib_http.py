import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pr_radar.adapters.github.http import GitHubHttpResponse, GitHubHttpTimeout


def urllib_http_get(
    url: str,
    *,
    headers: Mapping[str, str],
) -> GitHubHttpResponse:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read()
            response_headers = dict(response.headers.items())
            return GitHubHttpResponse(
                status_code=response.status,
                body=_response_body(response_body, response_headers),
                headers=response_headers,
            )
    except HTTPError as error:
        response_body = error.read()
        response_headers = dict(error.headers.items())
        return GitHubHttpResponse(
            status_code=error.code,
            body=_response_body(response_body, response_headers),
            headers=response_headers,
        )
    except TimeoutError as error:
        raise GitHubHttpTimeout("GitHub HTTP request timed out.") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise GitHubHttpTimeout("GitHub HTTP request timed out.") from error
        raise GitHubHttpTimeout("GitHub HTTP request failed.") from error


def _response_body(
    body: bytes,
    headers: Mapping[str, str],
) -> object:
    text = body.decode("utf-8", errors="replace")
    content_type = headers.get("Content-Type", headers.get("content-type", ""))
    if "json" not in content_type.lower():
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
