from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, TypeAlias

from pydantic import Field, field_serializer, field_validator

from pr_radar.contracts.base import StrictContract
from pr_radar.contracts.decisions import DecisionSource
from pr_radar.contracts.findings import FindingStatus
from pr_radar.contracts.inputs import PrInput
from pr_radar.contracts.references import (
    EvidenceReference,
    EvidenceReferenceKind,
    RedactedExcerpt,
)


GitHubChangedFileStatus: TypeAlias = Literal[
    "added",
    "modified",
    "removed",
    "renamed",
    "copied",
    "changed",
    "unchanged",
]
ChangedFileStatus: TypeAlias = GitHubChangedFileStatus
FetchFailureReason: TypeAlias = Literal[
    "missing_token",
    "unauthorized",
    "forbidden",
    "not_found",
    "timeout",
    "rate_limited",
    "unsupported_provider",
    "unsupported_deployment",
]
AiSignalType: TypeAlias = Literal[
    "bot_actor",
    "branch_prefix",
    "pr_signature",
    "repo_marker",
]
AiSignalStrength: TypeAlias = Literal["strong", "medium", "weak"]
AiSignalCalibrationReason: TypeAlias = Literal[
    "bot_identity_strong_ai_assistance_signal",
    "agent_branch_prefix_medium_ai_assistance_signal",
    "explicit_pr_body_signature_strong_ai_assistance_signal",
    "repo_marker_weak_project_level_signal",
]


class PrMetadata(StrictContract):
    title: str
    body: str
    author_login: str
    head_ref: str
    base_ref: str
    labels: tuple[str, ...] = ()


class CommitMetadata(StrictContract):
    sha: str
    author_login: str
    committer_login: str
    message: str


class ChangedFileMetadata(StrictContract):
    path: str
    status: GitHubChangedFileStatus
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)


class RawEvidence(StrictContract):
    diff: str
    file_contents: Mapping[str, str] = Field(
        default_factory=dict,
        validate_default=True,
    )

    @field_validator("file_contents", mode="after")
    @classmethod
    def freeze_file_contents(
        cls,
        file_contents: Mapping[str, str],
    ) -> Mapping[str, str]:
        return MappingProxyType(dict(file_contents))

    @field_serializer("file_contents")
    def serialize_file_contents(
        self,
        file_contents: Mapping[str, str],
    ) -> dict[str, str]:
        return dict(file_contents)


class FetchFailure(StrictContract):
    reason: FetchFailureReason
    message: str


class AiSignalFinding(StrictContract):
    signal_type: AiSignalType
    strength: AiSignalStrength
    title: str
    status: FindingStatus = "info"
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[EvidenceReference, ...]
    redacted_excerpts: tuple[RedactedExcerpt, ...] = ()
    decision_source: DecisionSource
    calibration_reason: AiSignalCalibrationReason
    tags: tuple[str, ...] = ()


class PrEvidencePack(StrictContract):
    pr_input: PrInput
    pr_metadata: PrMetadata
    commits: tuple[CommitMetadata, ...] = ()
    changed_files: tuple[ChangedFileMetadata, ...] = ()
    raw_evidence: RawEvidence
    evidence_refs: tuple[EvidenceReference, ...] = ()
    redacted_excerpts: tuple[RedactedExcerpt, ...] = ()
