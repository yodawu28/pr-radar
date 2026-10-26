from typing import Literal, TypeAlias

from pr_radar.contracts.base import StrictContract


EvidenceReferenceKind: TypeAlias = Literal[
    "pr",
    "commit",
    "file",
    "repo_file",
    "diff",
]


class EvidenceReference(StrictContract):
    kind: EvidenceReferenceKind
    ref: str


class RedactedExcerpt(StrictContract):
    evidence_ref: EvidenceReference
    text: str
