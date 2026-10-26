import re

from pr_radar.contracts import EvidenceReference, RedactedExcerpt


MAX_REDACTED_EXCERPT_LENGTH = 240

_AUTHORIZATION_BEARER_RE = re.compile(
    r"(Authorization\s*:\s*[A-Za-z][A-Za-z0-9_-]*\s+)\S+",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(?P<key>"
    r"api[_-]?key|service[_-]?token|access[_-]?token|refresh[_-]?token|"
    r"private[_-]?key|secret|password|token"
    r")(?P<sep>\s*[:=]\s*)\S+",
    re.IGNORECASE,
)
_URL_USERINFO_RE = re.compile(
    r"(?P<scheme>https?://)[^\s/@:]+(?::[^\s/@]*)?@(?P<host>[^\s/]+)",
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SENSITIVE_INTERNAL_URL_RE = re.compile(
    r"(?P<scheme>https?)://(?:[^\s/@]+(?::[^\s/@]*)?@)?"
    r"(?:git\.linecorp\.com|ghe\.corp\.yahoo\.co\.jp)"
    r"(?:/[^\s]*)?",
)


def redact_excerpt(
    *,
    evidence_ref: EvidenceReference,
    text: str,
) -> RedactedExcerpt:
    return RedactedExcerpt(
        evidence_ref=evidence_ref,
        text=redact_text(text),
    )


def redact_text(text: str, *, limit: bool = True) -> str:
    redacted = _SENSITIVE_INTERNAL_URL_RE.sub(
        r"\g<scheme>://<REDACTED_INTERNAL_URL>",
        text,
    )
    redacted = _URL_USERINFO_RE.sub(
        r"\g<scheme><REDACTED_CREDENTIALS>@\g<host>",
        redacted,
    )
    redacted = _AUTHORIZATION_BEARER_RE.sub(
        r"\1<REDACTED_TOKEN>",
        redacted,
    )
    redacted = _SECRET_ASSIGNMENT_RE.sub(
        r"\g<key>\g<sep><REDACTED_SECRET>",
        redacted,
    )
    redacted = _EMAIL_RE.sub("<REDACTED_EMAIL>", redacted)
    if not limit:
        return redacted
    return _limit_excerpt(redacted)


def _limit_excerpt(text: str) -> str:
    if len(text) <= MAX_REDACTED_EXCERPT_LENGTH:
        return text

    return f"{text[: MAX_REDACTED_EXCERPT_LENGTH - 3].rstrip()}..."
