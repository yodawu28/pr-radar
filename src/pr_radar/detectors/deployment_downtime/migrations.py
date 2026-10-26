from dataclasses import dataclass

from pr_radar.contracts import Finding, FindingStatus, PrEvidencePack
from pr_radar.detectors._shared.diff_blocks import added_lines, file_diff_block
from pr_radar.pull_requests.file_taxonomy import is_sql_migration


_MIGRATION_TAG = "detector:migration"
_DESTRUCTIVE_TAG = "migration:destructive"
_LOW_CONFIDENCE_TAG = "low confidence"

_DESTRUCTIVE_SQL_CLUES = (
    "drop column",
    "drop table",
    "truncate table",
)
_AMBIGUOUS_HIGH_IMPACT_SQL_CLUES = (
    "alter column",
    "set not null",
)


@dataclass(frozen=True)
class _Calibration:
    status: FindingStatus
    score: int
    confidence: float
    reason: str


_DESTRUCTIVE_CALIBRATION = _Calibration(
    status="high",
    score=88,
    confidence=0.86,
    reason="destructive_migration_data_loss_risk",
)
_AMBIGUOUS_HIGH_IMPACT_CALIBRATION = _Calibration(
    status="warning",
    score=62,
    confidence=0.55,
    reason="ambiguous_migration_high_impact_low_confidence",
)


def detect_migration_risks(
    evidence_pack: PrEvidencePack,
) -> tuple[Finding, ...]:
    """Detect destructive or high-impact migration changes."""
    findings: list[Finding] = []

    for changed_file in evidence_pack.changed_files:
        if changed_file.status == "removed" or not is_sql_migration(changed_file.path):
            continue

        file_diff = file_diff_block(
            path=changed_file.path,
            diff=evidence_pack.raw_evidence.diff,
        )
        if not file_diff:
            continue

        added_sql_lines = tuple(added_lines(file_diff))
        normalized_added_sql = "\n".join(added_sql_lines).lower()
        if not normalized_added_sql:
            continue

        evidence_refs = (
            f"file:{changed_file.path}",
            f"diff:{changed_file.path}",
        )
        if _contains_any(normalized_added_sql, _DESTRUCTIVE_SQL_CLUES):
            findings.append(
                Finding(
                    id="migration.destructive.schema_change",
                    pillar="deployment_downtime",
                    title="Destructive migration requires deployment review",
                    status=_DESTRUCTIVE_CALIBRATION.status,
                    score=_DESTRUCTIVE_CALIBRATION.score,
                    confidence=_DESTRUCTIVE_CALIBRATION.confidence,
                    evidence_refs=evidence_refs,
                    decision_source="deterministic",
                    calibration_reason=_DESTRUCTIVE_CALIBRATION.reason,
                    tags=(_MIGRATION_TAG, _DESTRUCTIVE_TAG),
                ),
            )
            continue

        if _contains_any(normalized_added_sql, _AMBIGUOUS_HIGH_IMPACT_SQL_CLUES):
            findings.append(
                Finding(
                    id="migration.ambiguous.high_impact_schema_change",
                    pillar="deployment_downtime",
                    title="High-impact migration pattern needs review",
                    status=_AMBIGUOUS_HIGH_IMPACT_CALIBRATION.status,
                    score=_AMBIGUOUS_HIGH_IMPACT_CALIBRATION.score,
                    confidence=_AMBIGUOUS_HIGH_IMPACT_CALIBRATION.confidence,
                    evidence_refs=evidence_refs,
                    decision_source="deterministic",
                    calibration_reason=_AMBIGUOUS_HIGH_IMPACT_CALIBRATION.reason,
                    tags=(_MIGRATION_TAG, _LOW_CONFIDENCE_TAG),
                ),
            )

    return tuple(findings)


def _contains_any(value: str, clues: tuple[str, ...]) -> bool:
    return any(clue in value for clue in clues)
