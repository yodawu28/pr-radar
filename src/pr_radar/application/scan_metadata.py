from typing import Literal, TypeAlias

from pydantic import Field

from pr_radar.contracts import metadata_keys
from pr_radar.contracts.base import StrictContract


ContextEnvelopeStatus: TypeAlias = Literal["available", "unavailable"]
ContextGrade: TypeAlias = Literal["parser_only", "review_grade", "unavailable"]
BlastRadiusAvailability: TypeAlias = Literal["available", "partial", "unavailable"]


class ScanEvaluationMetadata(StrictContract):
    context_grade: ContextGrade
    context_envelope: ContextEnvelopeStatus
    context_finding_count: int = Field(ge=0)
    context_budget_max_chars: int = Field(ge=0)
    context_budget_used_chars: int = Field(ge=0)
    context_budget_is_over_budget: bool
    blast_radius_context_grade: ContextGrade
    blast_radius_availability: BlastRadiusAvailability
    blast_radius_reason_code: str
    blast_radius_dependent_count: int = Field(ge=0)
    blast_radius_truncated: bool
    blast_radius_changed_paths: tuple[str, ...] = ()
    blast_radius_direct_dependents: tuple[str, ...] = ()

    def to_report_metadata(self) -> dict[str, str]:
        return {
            metadata_keys.CONTEXT_GRADE: self.context_grade,
            metadata_keys.CONTEXT_ENVELOPE: self.context_envelope,
            metadata_keys.CONTEXT_FINDING_COUNT: str(self.context_finding_count),
            metadata_keys.CONTEXT_BUDGET_MAX_CHARS: str(
                self.context_budget_max_chars,
            ),
            metadata_keys.CONTEXT_BUDGET_USED_CHARS: str(
                self.context_budget_used_chars,
            ),
            metadata_keys.CONTEXT_BUDGET_IS_OVER_BUDGET: str(
                self.context_budget_is_over_budget,
            ),
            metadata_keys.BLAST_RADIUS_CONTEXT_GRADE: (
                self.blast_radius_context_grade
            ),
            metadata_keys.BLAST_RADIUS_AVAILABILITY: self.blast_radius_availability,
            metadata_keys.BLAST_RADIUS_REASON_CODE: self.blast_radius_reason_code,
            metadata_keys.BLAST_RADIUS_DEPENDENT_COUNT: str(
                self.blast_radius_dependent_count,
            ),
            metadata_keys.BLAST_RADIUS_TRUNCATED: str(self.blast_radius_truncated),
            metadata_keys.BLAST_RADIUS_CHANGED_PATHS: ",".join(
                self.blast_radius_changed_paths,
            ),
            metadata_keys.BLAST_RADIUS_DIRECT_DEPENDENTS: ",".join(
                self.blast_radius_direct_dependents,
            ),
        }
