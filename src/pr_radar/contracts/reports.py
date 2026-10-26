from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from pr_radar.contracts.base import StrictContract
from pr_radar.contracts.decisions import DecisionStatus
from pr_radar.contracts.findings import Finding
from pr_radar.contracts.inputs import PrInput


REPORT_SCHEMA_VERSION = "pr-radar.report.v1"


class Report(StrictContract):
    schema_version: Literal["pr-radar.report.v1"] = REPORT_SCHEMA_VERSION
    overall_status: DecisionStatus
    pr_input: PrInput
    ai_signal_summary: str
    findings: tuple[Finding, ...] = ()
    low_confidence_findings: tuple[Finding, ...] = ()
    evaluation_metadata: Mapping[str, str] = Field(
        default_factory=dict,
        validate_default=True,
    )

    @field_validator("evaluation_metadata", mode="after")
    @classmethod
    def freeze_evaluation_metadata(
        cls,
        evaluation_metadata: Mapping[str, str],
    ) -> Mapping[str, str]:
        return MappingProxyType(dict(evaluation_metadata))

    @field_serializer("evaluation_metadata")
    def serialize_evaluation_metadata(
        self,
        evaluation_metadata: Mapping[str, str],
    ) -> dict[str, str]:
        return dict(evaluation_metadata)
