from typing import Literal

from pydantic import Field

from pr_radar.contracts.base import StrictContract
from pr_radar.contracts.decisions import DecisionSource
from pr_radar.contracts.references import RedactedExcerpt


FindingStatus = Literal["info", "warning", "high", "critical"]


class Finding(StrictContract):
    id: str
    pillar: str
    title: str
    status: FindingStatus
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...]
    decision_source: DecisionSource
    calibration_reason: str | None = None
    tags: tuple[str, ...] = ()
    redacted_excerpts: tuple[RedactedExcerpt, ...] = ()
