from dataclasses import dataclass

from pr_radar.contracts import Finding, FindingStatus, PrEvidencePack
from pr_radar.detectors._shared.diff_blocks import added_lines, file_diff_block
from pr_radar.pull_requests.file_taxonomy import (
    DependencyManifestKind,
    dependency_manifest_kind,
)


_DEPENDENCY_TAG = "detector:dependency"


@dataclass(frozen=True)
class _Calibration:
    status: FindingStatus
    score: int
    confidence: float
    reason: str


_ADDED_MANIFEST_CALIBRATION = _Calibration(
    status="warning",
    score=68,
    confidence=0.74,
    reason="dependency_added_manifest_requires_supply_chain_review",
)


def detect_dependency_additions(
    evidence_pack: PrEvidencePack,
) -> tuple[Finding, ...]:
    """Detect new dependency declarations from review-grade PR evidence."""
    findings: list[Finding] = []

    for changed_file in evidence_pack.changed_files:
        if changed_file.status == "removed":
            continue

        manifest = dependency_manifest_kind(changed_file.path)
        if manifest is None:
            continue
        if not _has_dependency_addition(
            manifest=manifest,
            path=changed_file.path,
            diff=evidence_pack.raw_evidence.diff,
        ):
            continue

        findings.append(
            Finding(
                id=f"dependency.added.{manifest}",
                pillar="security_supply_chain",
                title="New dependency requires supply-chain review",
                status=_ADDED_MANIFEST_CALIBRATION.status,
                score=_ADDED_MANIFEST_CALIBRATION.score,
                confidence=_ADDED_MANIFEST_CALIBRATION.confidence,
                evidence_refs=(
                    f"file:{changed_file.path}",
                    f"diff:{changed_file.path}",
                ),
                decision_source="deterministic",
                calibration_reason=_ADDED_MANIFEST_CALIBRATION.reason,
                tags=(_DEPENDENCY_TAG,),
            ),
        )

    return tuple(findings)


def _has_dependency_addition(
    *,
    manifest: DependencyManifestKind,
    path: str,
    diff: str,
) -> bool:
    file_diff = file_diff_block(path=path, diff=diff)
    if not file_diff:
        return False

    normalized_diff = file_diff.lower()
    added_dependency_lines = tuple(added_lines(file_diff))
    if not added_dependency_lines:
        return False

    if manifest == "pyproject":
        return "dependencies" in normalized_diff and any(
            _looks_like_pyproject_dependency(line) for line in added_dependency_lines
        )
    if manifest == "package_json":
        return "dependencies" in normalized_diff and any(
            _looks_like_package_json_dependency(line)
            for line in added_dependency_lines
        )
    return False


def _looks_like_pyproject_dependency(line: str) -> bool:
    return line.startswith(('"', "'")) and any(
        operator in line for operator in (">", "=", "~")
    )


def _looks_like_package_json_dependency(line: str) -> bool:
    return line.startswith('"') and '":' in line
