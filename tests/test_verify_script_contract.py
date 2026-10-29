import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify.sh"
AGENTS_GUIDE = PROJECT_ROOT / "AGENTS.md"
UNIT_TEST_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "unit-tests.yml"
GITIGNORE = PROJECT_ROOT / ".gitignore"
EVALUATION_CASES_README = PROJECT_ROOT / "evaluation" / "bench" / "cases" / "README.md"
PUBLIC_EVALUATION_CASES = PROJECT_ROOT / "evaluation" / "bench" / "cases" / "public"
PUBLIC_SAMPLE_MANIFEST = PUBLIC_EVALUATION_CASES / "synthetic-dependency-change.yaml"
PUBLIC_SCHEMA_DOC = PUBLIC_EVALUATION_CASES / "schema.md"


def test_verify_success_message_is_after_all_fail_closed_guards() -> None:
    """Prevents the canonical verifier from claiming success before late guards."""
    script = VERIFY_SCRIPT.read_text()

    success_message_index = script.index("VERIFY PASSED")
    final_guard_success_index = script.index("Context size within healthy thresholds")

    assert success_message_index > final_guard_success_index


def test_verify_context_thresholds_are_single_source_and_policy_aligned() -> None:
    """Prevents context guard constants from drifting away from harness policy."""
    script = VERIFY_SCRIPT.read_text()

    assert _shell_constant(script, "MAX_AGENTS_LINES") == 150
    assert "AGENTS.md must stay under $MAX_AGENTS_LINES lines" in script
    assert _shell_constant(script, "MAX_PROGRESS_LINES") == 250
    assert '[[ -f "AGENTS.md" && -f "PROGRESS.md" && -f "DECISIONS.md" ]]' in script
    if AGENTS_GUIDE.exists():
        agents = AGENTS_GUIDE.read_text()
        assert "PROGRESS.md" in agents
        assert "250" in agents


def test_verify_does_not_require_ripgrep_on_ci_runners() -> None:
    """Prevents GitHub Actions from failing when ripgrep is not preinstalled."""
    script = VERIFY_SCRIPT.read_text()

    assert "command -v rg" in script
    assert "grep -Eq" in script
    assert "find_markdown_tabs()" in script
    assert "xargs -0 grep -n" in script


def test_github_action_uses_resolvable_setup_uv_ref() -> None:
    """Prevents CI from using an unresolved setup-uv major tag."""
    workflow = UNIT_TEST_WORKFLOW.read_text()

    assert "astral-sh/setup-uv@v10" not in workflow
    assert re.search(
        r"uses:\s+astral-sh/setup-uv@[0-9a-f]{40}\s+#\s+v\d+\.\d+\.\d+",
        workflow,
    )


def test_evaluation_data_boundary_is_documented_and_private_paths_ignored() -> None:
    """Locks the Sprint 5 evaluation data boundary before contract work starts."""
    gitignore = GITIGNORE.read_text()

    assert "evaluation/outputs/" in gitignore
    assert "evaluation/bench/cases/private/" in gitignore

    readme = EVALUATION_CASES_README.read_text()
    required_patterns = [
        "Aimigo",
        "ground_truth.json",
        "patch.diff",
        "PR_TITLE",
        "PR_BODY",
        "partial",
        "unavailable",
        "severity normalization",
        "critical/high/error",
        "medium/warn/warning",
        "low/info/success",
        "private",
        "public",
        "raw local input",
        "must not be synced",
    ]

    for pattern in required_patterns:
        assert pattern in readme


def test_public_synthetic_evaluation_case_and_schema_are_publishable() -> None:
    """Locks the public/private benchmark boundary for public repository sync."""
    from pr_radar.evaluation.manifest_loader import load_evaluation_manifest

    assert PUBLIC_SAMPLE_MANIFEST.exists()
    assert PUBLIC_SCHEMA_DOC.exists()

    cases = load_evaluation_manifest(PUBLIC_SAMPLE_MANIFEST)
    assert len(cases) == 1
    public_case = cases[0]
    assert public_case.case_id == "public-synthetic-dependency-change"
    assert public_case.source_format == "synthetic_replay"
    assert public_case.ruleset_version == "synthetic-v1"
    assert public_case.source_refs == ("sample-manifest.yaml:sha256:publiccase001",)
    assert public_case.expected_findings[0].severity == "high_risk"

    schema_doc = PUBLIC_SCHEMA_DOC.read_text()
    required_schema_terms = (
        "case_id",
        "source_format",
        "pr_id",
        "source_refs",
        "expected_findings",
        "finding_id",
        "pillar",
        "reason_code",
        "evidence_path",
        "severity",
        "source_excerpt_hash",
        "content-free",
        "no raw diff",
        "no internal URLs",
    )
    for term in required_schema_terms:
        assert term in schema_doc

    combined_public_text = "\n".join(
        path.read_text() for path in sorted(PUBLIC_EVALUATION_CASES.rglob("*"))
        if path.is_file()
    )
    forbidden_public_fragments = (
        "diff --git",
        "PRIVATE_RAW_SOURCE",
        "api_key=sk_live",
        "https://git.linecorp.com",
        "ghe.corp.yahoo.co.jp",
    )
    for forbidden_fragment in forbidden_public_fragments:
        assert forbidden_fragment not in combined_public_text


def test_public_evaluation_case_tree_excludes_raw_benchmark_artifacts() -> None:
    """Prevents raw Aimigo fixture files from being synced through public cases."""
    forbidden_names = {
        "patch.diff",
        "ground_truth.json",
        "PR_BODY",
        "PR_BODY.md",
        "PR_BODY.txt",
        "PR_TITLE",
        "PR_TITLE.txt",
    }

    public_filenames = {
        path.name for path in PUBLIC_EVALUATION_CASES.rglob("*") if path.is_file()
    }

    assert public_filenames.isdisjoint(forbidden_names)


def _shell_constant(script: str, name: str) -> int:
    matches = re.findall(rf"^{name}=(\d+)$", script, flags=re.MULTILINE)

    assert len(matches) == 1
    return int(matches[0])
