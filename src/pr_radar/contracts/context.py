from typing import Literal

from pydantic import Field

from pr_radar.contracts.base import StrictContract
from pr_radar.contracts.blast_radius import BlastRadiusSummary


CONTEXT_ENVELOPE_SCHEMA_VERSION = "pr-radar.context-envelope.v1"
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
    schema_version: Literal[
        "pr-radar.context-envelope.v1"
    ] = CONTEXT_ENVELOPE_SCHEMA_VERSION
    context_grade: ContextGrade
    budget: ContextBudget
    items: tuple[ContextEnvelopeItem, ...] = ()
    omitted_finding_ids: tuple[str, ...] = ()
    blast_radius_summary: BlastRadiusSummary | None = None
