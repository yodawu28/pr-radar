from dataclasses import dataclass

from pr_radar.contracts import (
    EvidenceReference,
    Finding,
    FindingStatus,
    PrEvidencePack,
)
from pr_radar.detectors._shared.diff_blocks import added_lines, file_diff_block
from pr_radar.privacy.redaction import redact_excerpt
from pr_radar.pull_requests.file_taxonomy import is_source_path, is_test_path


_TEST_SHAPE_TAG = "detector:test_shape"
_LOW_CONFIDENCE_TAG = "low confidence"
_DISABLED_TEST_TAG = "test:disabled"

_DISABLED_TEST_CLUES = (
    "pytest.mark.skip",
    "@unittest.skip",
    ".skip(",
    "test.skip(",
    "describe.skip(",
    "xit(",
    "xdescribe(",
)


@dataclass(frozen=True)
class _Calibration:
    status: FindingStatus
    score: int
    confidence: float
    reason: str


_DISABLED_TEST_CALIBRATION = _Calibration(
    status="warning",
    score=66,
    confidence=0.68,
    reason="disabled_test_reduces_test_integrity",
)
_MISSING_BEHAVIOR_COVERAGE_CALIBRATION = _Calibration(
    status="warning",
    score=58,
    confidence=0.52,
    reason="behavior_change_without_test_evidence_low_confidence",
)
_BEHAVIOR_CLUES = (
    "if ",
    "elif ",
    "else:",
    "raise ",
    "return ",
    "for ",
    "while ",
    "try:",
    "except ",
    "await ",
    "yield ",
    "def ",
    "class ",
)


def detect_test_shape_risks(
    evidence_pack: PrEvidencePack,
) -> tuple[Finding, ...]:
    """Detect reportable test-shape risks from review-grade PR evidence."""
    findings: list[Finding] = []
    has_test_change = any(
        changed_file.status != "removed" and is_test_path(changed_file.path)
        for changed_file in evidence_pack.changed_files
    )

    for changed_file in evidence_pack.changed_files:
        if changed_file.status == "removed":
            continue

        file_diff = file_diff_block(
            path=changed_file.path,
            diff=evidence_pack.raw_evidence.diff,
        )
        if not file_diff:
            continue

        added = added_lines(file_diff)
        if is_test_path(changed_file.path):
            disabled_line = _first_disabled_test_line(added)
            if disabled_line is not None:
                findings.append(
                    _disabled_test_finding(
                        path=changed_file.path,
                        disabled_line=disabled_line,
                    ),
                )
            continue

        if has_test_change or not is_source_path(changed_file.path):
            continue
        if not _has_behavior_change(added):
            continue

        findings.append(_missing_behavior_coverage_finding(changed_file.path))

    return tuple(findings)


def _disabled_test_finding(*, path: str, disabled_line: str) -> Finding:
    evidence_ref = EvidenceReference(kind="diff", ref=f"diff:{path}")
    return Finding(
        id="test_shape.disabled_test",
        pillar="test_integrity",
        title="Disabled test requires review",
        status=_DISABLED_TEST_CALIBRATION.status,
        score=_DISABLED_TEST_CALIBRATION.score,
        confidence=_DISABLED_TEST_CALIBRATION.confidence,
        evidence_refs=(f"file:{path}", f"diff:{path}"),
        decision_source="deterministic",
        calibration_reason=_DISABLED_TEST_CALIBRATION.reason,
        tags=(_TEST_SHAPE_TAG, _DISABLED_TEST_TAG),
        redacted_excerpts=(
            redact_excerpt(evidence_ref=evidence_ref, text=disabled_line),
        ),
    )


def _missing_behavior_coverage_finding(path: str) -> Finding:
    return Finding(
        id="test_shape.missing_behavior_coverage",
        pillar="test_integrity",
        title="Behavior change has no nearby test evidence",
        status=_MISSING_BEHAVIOR_COVERAGE_CALIBRATION.status,
        score=_MISSING_BEHAVIOR_COVERAGE_CALIBRATION.score,
        confidence=_MISSING_BEHAVIOR_COVERAGE_CALIBRATION.confidence,
        evidence_refs=(f"file:{path}", f"diff:{path}"),
        decision_source="deterministic",
        calibration_reason=_MISSING_BEHAVIOR_COVERAGE_CALIBRATION.reason,
        tags=(_TEST_SHAPE_TAG, _LOW_CONFIDENCE_TAG),
    )


def _first_disabled_test_line(lines: tuple[str, ...]) -> str | None:
    for line in lines:
        normalized_line = line.lower()
        if any(clue in normalized_line for clue in _DISABLED_TEST_CLUES):
            return line
    return None


def _has_behavior_change(lines: tuple[str, ...]) -> bool:
    return any(_is_behavior_line(line) for line in lines)


def _is_behavior_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", '"""', "'''", "*", "//", "/*")):
        return False
    normalized_line = stripped.lower()
    if normalized_line.startswith(("import ", "from ")):
        return False
    return any(clue in normalized_line for clue in _BEHAVIOR_CLUES)
