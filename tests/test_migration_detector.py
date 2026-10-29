from pr_radar.contracts import (
    ChangedFileMetadata,
    GitHubChangedFileStatus,
    PrEvidencePack,
    PrInput,
    PrMetadata,
    RawEvidence,
    LOW_CONFIDENCE_TAG,
)
from pr_radar.detectors.deployment_downtime.migrations import detect_migration_risks
from pr_radar.detectors.static_risk import run_static_detectors


def _evidence_pack(
    *,
    path: str,
    diff: str,
    file_contents: dict[str, str] | None = None,
    status: GitHubChangedFileStatus = "modified",
) -> PrEvidencePack:
    return PrEvidencePack(
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        pr_metadata=PrMetadata(
            title="Update database migration",
            body="",
            author_login="alice",
            head_ref="agent/schema-migration",
            base_ref="main",
        ),
        changed_files=(
            ChangedFileMetadata(
                path=path,
                status=status,
                additions=diff.count("\n+"),
                deletions=diff.count("\n-"),
            ),
        ),
        raw_evidence=RawEvidence(
            diff=diff,
            file_contents=file_contents or {},
        ),
    )


def test_migration_detector_flags_destructive_sql_schema_changes() -> None:
    """Catches explicit data-loss operations before deployment."""
    result = run_static_detectors(
        _evidence_pack(
            path="db/migrations/20261025090000_drop_legacy_users.sql",
            diff=(
                "diff --git a/db/migrations/20261025090000_drop_legacy_users.sql "
                "b/db/migrations/20261025090000_drop_legacy_users.sql\n"
                "@@ destructive migration @@\n"
                "+ALTER TABLE users DROP COLUMN legacy_id;\n"
                "+DROP TABLE old_sessions;\n"
            ),
            file_contents={
                "db/migrations/20261025090000_drop_legacy_users.sql": (
                    "ALTER TABLE users DROP COLUMN legacy_id;\n"
                    "DROP TABLE old_sessions;\n"
                ),
            },
        ),
        detectors=(detect_migration_risks,),
        context_max_chars=2_000,
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "migration.destructive.schema_change"
    assert finding.pillar == "deployment_downtime"
    assert finding.status == "high"
    assert finding.score >= 80
    assert finding.confidence >= 0.8
    assert finding.evidence_refs == (
        "file:db/migrations/20261025090000_drop_legacy_users.sql",
        "diff:db/migrations/20261025090000_drop_legacy_users.sql",
    )
    assert finding.decision_source == "deterministic"
    assert finding.calibration_reason == "destructive_migration_data_loss_risk"
    assert finding.tags == ("detector:migration", "migration:destructive")
    assert result.context_envelope.items[0].detector_id == "migration"


def test_migration_detector_flags_ambiguous_high_impact_schema_changes() -> None:
    """Keeps risky but ambiguous schema changes visible as low-confidence."""
    findings = detect_migration_risks(
        _evidence_pack(
            path="db/migrations/20261025090100_rewrite_orders.sql",
            diff=(
                "diff --git a/db/migrations/20261025090100_rewrite_orders.sql "
                "b/db/migrations/20261025090100_rewrite_orders.sql\n"
                "@@ high impact migration @@\n"
                "+ALTER TABLE orders ALTER COLUMN amount TYPE BIGINT;\n"
                "+ALTER TABLE orders ALTER COLUMN status SET NOT NULL;\n"
            ),
            file_contents={
                "db/migrations/20261025090100_rewrite_orders.sql": (
                    "ALTER TABLE orders ALTER COLUMN amount TYPE BIGINT;\n"
                    "ALTER TABLE orders ALTER COLUMN status SET NOT NULL;\n"
                ),
            },
        ),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.id == "migration.ambiguous.high_impact_schema_change"
    assert finding.pillar == "deployment_downtime"
    assert finding.status == "warning"
    assert 50 <= finding.score < 80
    assert 0.4 <= finding.confidence < 0.7
    assert finding.evidence_refs == (
        "file:db/migrations/20261025090100_rewrite_orders.sql",
        "diff:db/migrations/20261025090100_rewrite_orders.sql",
    )
    assert finding.decision_source == "deterministic"
    assert finding.calibration_reason == (
        "ambiguous_migration_high_impact_low_confidence"
    )
    assert finding.tags == ("detector:migration", LOW_CONFIDENCE_TAG)


def test_migration_detector_ignores_safe_additive_migrations() -> None:
    """Prevents additive schema changes from becoming noisy findings."""
    findings = detect_migration_risks(
        _evidence_pack(
            path="db/migrations/20261025090200_add_user_timezone.sql",
            diff=(
                "diff --git a/db/migrations/20261025090200_add_user_timezone.sql "
                "b/db/migrations/20261025090200_add_user_timezone.sql\n"
                "@@ additive migration @@\n"
                "+ALTER TABLE users ADD COLUMN timezone VARCHAR(64);\n"
            ),
            file_contents={
                "db/migrations/20261025090200_add_user_timezone.sql": (
                    "ALTER TABLE users ADD COLUMN timezone VARCHAR(64);\n"
                ),
            },
        ),
    )

    assert findings == ()
