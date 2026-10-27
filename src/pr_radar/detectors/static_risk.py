import re
from collections.abc import Callable, Mapping, Sequence

from pr_radar.application.context import ContextEnvelope, build_context_envelope
from pr_radar.contracts import BlastRadiusSummary, Finding, PrEvidencePack
from pr_radar.contracts.base import StrictContract
from pr_radar.privacy.redaction import redact_text


StaticDetector = Callable[[PrEvidencePack], tuple[Finding, ...]]

_STABLE_FINDING_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


class DetectorContractError(ValueError):
    """Raised when a detector emits output unsafe for reports or evaluation."""


class StaticDetectorResult(StrictContract):
    findings: tuple[Finding, ...]
    context_envelope: ContextEnvelope


def run_static_detectors(
    evidence_pack: PrEvidencePack,
    *,
    detectors: Sequence[StaticDetector],
    context_max_chars: int,
    blast_radius_summary: BlastRadiusSummary | None = None,
) -> StaticDetectorResult:
    findings: list[Finding] = []
    detector_ids_by_finding_id: dict[str, str] = {}
    raw_fragments = _raw_fragments(evidence_pack)

    for detector in detectors:
        for finding in detector(evidence_pack):
            _validate_finding(finding, raw_fragments)
            findings.append(finding)
            detector_ids_by_finding_id[finding.id] = _detector_id(finding, detector)

    return StaticDetectorResult(
        findings=tuple(findings),
        context_envelope=build_context_envelope(
            findings=findings,
            detector_id="static",
            detector_ids_by_finding_id=detector_ids_by_finding_id,
            max_chars=context_max_chars,
            blast_radius_summary=blast_radius_summary,
        ),
    )


def _validate_finding(
    finding: Finding,
    raw_fragments: tuple[str, ...],
) -> None:
    if _STABLE_FINDING_ID_RE.fullmatch(finding.id) is None:
        raise DetectorContractError(
            f"Finding {finding.id!r} must use a stable finding id.",
        )

    report_fields = (
        finding.id,
        finding.pillar,
        finding.title,
        finding.calibration_reason,
        *finding.evidence_refs,
        *finding.tags,
    )
    if any(
        field is not None and _contains_raw_evidence(field, raw_fragments)
        for field in report_fields
    ):
        raise DetectorContractError(
            f"Finding {finding.id!r} contains raw evidence.",
        )

    for excerpt in finding.redacted_excerpts:
        _validate_redacted_excerpt(finding=finding, text=excerpt.text)


def _contains_raw_evidence(
    value: str,
    raw_fragments: tuple[str, ...],
) -> bool:
    if "diff --git" in value:
        return True
    return any(fragment and fragment in value for fragment in raw_fragments)


def _validate_redacted_excerpt(*, finding: Finding, text: str) -> None:
    if "diff --git" in text or redact_text(text) != text:
        raise DetectorContractError(
            f"Finding {finding.id!r} contains unredacted excerpt evidence.",
        )


def _raw_fragments(evidence_pack: PrEvidencePack) -> tuple[str, ...]:
    raw_blobs = (
        evidence_pack.raw_evidence.diff,
        *evidence_pack.raw_evidence.file_contents.values(),
    )
    raw_lines = tuple(
        line
        for raw_blob in raw_blobs
        for line in _meaningful_raw_lines(raw_blob)
    )
    return raw_blobs + raw_lines


def _meaningful_raw_lines(raw_blob: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in raw_blob.splitlines()
        if len(line.strip()) >= 8
    )


def _detector_id(
    finding: Finding,
    detector: StaticDetector,
) -> str:
    for tag in finding.tags:
        if tag.startswith("detector:"):
            return tag.removeprefix("detector:")
    return _normalize_detector_name(detector.__name__)


def _normalize_detector_name(name: str) -> str:
    for suffix in ("_detector", "_findings", "_finding"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip("_") or "static"
