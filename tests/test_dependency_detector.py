from pr_radar.contracts import (
    ChangedFileMetadata,
    GitHubChangedFileStatus,
    PrEvidencePack,
    PrInput,
    PrMetadata,
    RawEvidence,
)
from pr_radar.detectors.security_supply_chain.dependencies import (
    detect_dependency_additions,
)
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
            title="Update dependencies",
            body="",
            author_login="alice",
            head_ref="agent/dependency-update",
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


def test_dependency_detector_flags_pyproject_dependency_additions() -> None:
    """Locks the first Python manifest signal without package-index lookups."""
    result = run_static_detectors(
        _evidence_pack(
            path="pyproject.toml",
            diff=(
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "@@ [project] dependencies @@\n"
                "+    \"requests>=2.32\",\n"
            ),
            file_contents={
                "pyproject.toml": (
                    "[project]\n"
                    "dependencies = [\n"
                    "    \"requests>=2.32\",\n"
                    "]\n"
                ),
            },
        ),
        detectors=(detect_dependency_additions,),
        context_max_chars=2_000,
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "dependency.added.pyproject"
    assert finding.pillar == "security_supply_chain"
    assert finding.status == "warning"
    assert finding.score >= 60
    assert finding.confidence >= 0.6
    assert finding.evidence_refs == ("file:pyproject.toml", "diff:pyproject.toml")
    assert finding.decision_source == "deterministic"
    assert finding.calibration_reason == (
        "dependency_added_manifest_requires_supply_chain_review"
    )
    assert finding.tags == ("detector:dependency",)
    assert result.context_envelope.items[0].detector_id == "dependency"


def test_dependency_detector_flags_package_json_dependency_additions() -> None:
    """Locks the first JavaScript manifest signal without package-index lookups."""
    result = run_static_detectors(
        _evidence_pack(
            path="package.json",
            diff=(
                "diff --git a/package.json b/package.json\n"
                "@@ \"dependencies\" @@\n"
                "+    \"lodash\": \"^4.17.21\"\n"
            ),
            file_contents={
                "package.json": (
                    "{\n"
                    "  \"dependencies\": {\n"
                    "    \"lodash\": \"^4.17.21\"\n"
                    "  }\n"
                    "}\n"
                ),
            },
        ),
        detectors=(detect_dependency_additions,),
        context_max_chars=2_000,
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "dependency.added.package_json"
    assert finding.pillar == "security_supply_chain"
    assert finding.evidence_refs == ("file:package.json", "diff:package.json")
    assert finding.calibration_reason == (
        "dependency_added_manifest_requires_supply_chain_review"
    )
    assert finding.tags == ("detector:dependency",)


def test_dependency_detector_isolates_file_diff_blocks_in_multi_file_pr() -> None:
    """Prevents one manifest's dependency hunk from tainting another file."""
    evidence_pack = PrEvidencePack(
        pr_input=PrInput(
            provider="github",
            deployment="github_com",
            repository="example/repo",
            pull_request_number=17,
            url="https://github.com/example/repo/pull/17",
        ),
        pr_metadata=PrMetadata(
            title="Update JavaScript dependency",
            body="",
            author_login="alice",
            head_ref="agent/dependency-update",
            base_ref="main",
        ),
        changed_files=(
            ChangedFileMetadata(
                path="pyproject.toml",
                status="modified",
                additions=1,
                deletions=0,
            ),
            ChangedFileMetadata(
                path="package.json",
                status="modified",
                additions=1,
                deletions=0,
            ),
        ),
        raw_evidence=RawEvidence(
            diff=(
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "@@ [project] @@\n"
                '+description = "Local tooling manifest"\n'
                "diff --git a/package.json b/package.json\n"
                '@@ "dependencies" @@\n'
                '+    "left-pad": ">=1.3.0"\n'
            ),
            file_contents={
                "pyproject.toml": '[project]\ndescription = "Local tooling manifest"\n',
                "package.json": (
                    "{\n"
                    '  "dependencies": {\n'
                    '    "left-pad": ">=1.3.0"\n'
                    "  }\n"
                    "}\n"
                ),
            },
        ),
    )

    findings = detect_dependency_additions(evidence_pack)

    assert tuple(finding.id for finding in findings) == (
        "dependency.added.package_json",
    )
    assert findings[0].evidence_refs == ("file:package.json", "diff:package.json")


def test_dependency_detector_ignores_unrelated_file_changes() -> None:
    """Prevents dependency detector noise outside supported manifests."""
    findings = detect_dependency_additions(
        _evidence_pack(
            path="src/app.py",
            diff=(
                "diff --git a/src/app.py b/src/app.py\n"
                "+DEPENDENCIES = ['requests']\n"
            ),
            file_contents={"src/app.py": "DEPENDENCIES = ['requests']\n"},
        ),
    )

    assert findings == ()


def test_dependency_detector_ignores_dependency_removals() -> None:
    """Prevents removals from being reported as added supply-chain risk."""
    findings = detect_dependency_additions(
        _evidence_pack(
            path="pyproject.toml",
            diff=(
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "@@ [project] dependencies @@\n"
                "-    \"requests>=2.32\",\n"
            ),
            file_contents={
                "pyproject.toml": (
                    "[project]\n"
                    "dependencies = []\n"
                ),
            },
        ),
    )

    assert findings == ()
