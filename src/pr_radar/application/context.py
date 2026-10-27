from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field

from pr_radar.contracts import BlastRadiusSummary, Finding
from pr_radar.contracts.base import StrictContract
from pr_radar.privacy.redaction import redact_text


ContextGrade = Literal["parser_only", "review_grade"]


class ContextBudget(StrictContract):
    max_chars: int = Field(ge=0)
    used_chars: int = Field(ge=0)
    is_over_budget: bool


class ContextEnvelopeItem(StrictContract):
    finding_id: str
    detector_id: str
    pillar: str
    title: str
    status: str
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...]
    calibration_reason: str | None = None
    redacted_excerpts: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class ContextEnvelope(StrictContract):
    context_grade: ContextGrade
    budget: ContextBudget
    items: tuple[ContextEnvelopeItem, ...] = ()
    omitted_finding_ids: tuple[str, ...] = ()
    blast_radius_summary: BlastRadiusSummary | None = None


def build_context_envelope(
    *,
    findings: Sequence[Finding],
    detector_id: str,
    max_chars: int,
    redacted_excerpts_by_finding_id: Mapping[str, Sequence[str]] | None = None,
    detector_ids_by_finding_id: Mapping[str, str] | None = None,
    blast_radius_summary: BlastRadiusSummary | None = None,
) -> ContextEnvelope:
    excerpts_by_finding_id = redacted_excerpts_by_finding_id or {}
    detector_ids = detector_ids_by_finding_id or {}
    items: list[ContextEnvelopeItem] = []
    omitted_finding_ids: list[str] = []
    used_chars = 0

    for finding in findings:
        item = ContextEnvelopeItem(
            finding_id=finding.id,
            detector_id=detector_ids.get(finding.id, detector_id),
            pillar=finding.pillar,
            title=finding.title,
            status=finding.status,
            score=finding.score,
            confidence=finding.confidence,
            evidence_refs=finding.evidence_refs,
            calibration_reason=finding.calibration_reason,
            redacted_excerpts=_redact_excerpts(
                excerpts_by_finding_id.get(
                    finding.id,
                    tuple(excerpt.text for excerpt in finding.redacted_excerpts),
                ),
            ),
            tags=finding.tags,
        )
        item_chars = _estimate_chars(item)
        if used_chars + item_chars > max_chars:
            omitted_finding_ids.append(finding.id)
            continue
        items.append(item)
        used_chars += item_chars

    return ContextEnvelope(
        context_grade="review_grade",
        budget=ContextBudget(
            max_chars=max_chars,
            used_chars=used_chars,
            is_over_budget=bool(omitted_finding_ids),
        ),
        items=tuple(items),
        omitted_finding_ids=tuple(omitted_finding_ids),
        blast_radius_summary=blast_radius_summary,
    )


def _estimate_chars(item: ContextEnvelopeItem) -> int:
    return len(str(item.model_dump(mode="json")))


def _redact_excerpts(excerpts: Sequence[str]) -> tuple[str, ...]:
    return tuple(redact_text(excerpt) for excerpt in excerpts)
