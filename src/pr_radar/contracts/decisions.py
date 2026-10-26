from typing import Literal

from pydantic import Field

from pr_radar.contracts.base import StrictContract


DecisionStatus = Literal["safe", "needs_attention", "high_risk", "blocker"]
DecisionSource = Literal[
    "deterministic",
    "kev_local",
    "hosted_llm",
    "unavailable",
]


class Decision(StrictContract):
    status: DecisionStatus
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()
    decision_source: DecisionSource
