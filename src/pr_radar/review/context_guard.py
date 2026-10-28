import re
from collections.abc import Iterable, Mapping

from pr_radar.contracts import ContextEnvelope
from pr_radar.contracts.base import StrictContract


RAW_DIFF_MARKER_REASON = "raw_diff_marker"
RAW_DIFF_HUNK_REASON = "raw_diff_hunk"
RAW_SOURCE_PAYLOAD_REASON = "raw_source_payload"
CREDENTIAL_LIKE_TOKEN_REASON = "credential_like_token"

_RAW_DIFF_MARKER_RE = re.compile(r"(?m)^(?:diff --git\b|--- [ab]/|\+\+\+ [ab]/)")
_RAW_DIFF_HUNK_RE = re.compile(
    r"(?m)^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@",
)
_RAW_SOURCE_DECLARATION_RE = re.compile(
    r"(?m)^\s*(?:async\s+def|def|class|function|const|let|var)\s+[A-Za-z_]\w*",
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|token)\s*[:=]\s*"
    r"['\"]?(?!<REDACTED_)[A-Za-z0-9][A-Za-z0-9_.-]{7,}",
)
_SECRET_VALUE_RE = re.compile(
    r"\b(?:sk|ghp|github_pat|xox[baprs])_[A-Za-z0-9_]{8,}\b",
)


class DecisionContextGuardResult(StrictContract):
    is_safe: bool
    reason_codes: tuple[str, ...] = ()


class DecisionContextRejected(ValueError):
    def __init__(self, reason_codes: Iterable[str]) -> None:
        self.reason_codes = tuple(sorted(set(reason_codes)))
        super().__init__(
            "decision context rejected: " + ", ".join(self.reason_codes),
        )


def validate_decision_context(
    context_envelope: ContextEnvelope,
) -> DecisionContextGuardResult:
    reason_codes = tuple(
        sorted(
            {
                reason_code
                for text in _string_values(context_envelope.model_dump(mode="json"))
                for reason_code in _detect_raw_context_reason_codes(text)
            },
        ),
    )

    if reason_codes:
        raise DecisionContextRejected(reason_codes)

    return DecisionContextGuardResult.model_validate({"is_safe": True})


def _detect_raw_context_reason_codes(text: str) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if _RAW_DIFF_MARKER_RE.search(text):
        reason_codes.append(RAW_DIFF_MARKER_REASON)
    if _RAW_DIFF_HUNK_RE.search(text):
        reason_codes.append(RAW_DIFF_HUNK_REASON)
    if "\n" in text and _RAW_SOURCE_DECLARATION_RE.search(text):
        reason_codes.append(RAW_SOURCE_PAYLOAD_REASON)
    if _CREDENTIAL_ASSIGNMENT_RE.search(text) or _SECRET_VALUE_RE.search(text):
        reason_codes.append(CREDENTIAL_LIKE_TOKEN_REASON)
    return tuple(reason_codes)


def _string_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            yield from _string_values(key)
            yield from _string_values(nested_value)
        return
    if isinstance(value, (list, tuple)):
        for nested_value in value:
            yield from _string_values(nested_value)
