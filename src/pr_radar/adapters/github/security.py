from urllib.parse import urlparse

from pr_radar.contracts import PrInput


def is_trusted_raw_file_url(
    raw_url: str,
    pr_input: PrInput,
) -> bool:
    parsed_raw_url = urlparse(raw_url)
    allowed_netlocs = raw_file_allowed_netlocs(pr_input)
    return (
        parsed_raw_url.scheme in {"http", "https"}
        and bool(parsed_raw_url.netloc)
        and parsed_raw_url.username is None
        and parsed_raw_url.password is None
        and parsed_raw_url.netloc.lower() in allowed_netlocs
    )


def raw_file_allowed_netlocs(
    pr_input: PrInput,
) -> set[str]:
    allowed_netlocs = {
        parsed.netloc.lower()
        for parsed in (urlparse(pr_input.url),)
        if parsed.netloc
    }
    if pr_input.deployment == "github_com":
        allowed_netlocs.add("raw.githubusercontent.com")
    return allowed_netlocs
