from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
SPRINT5_ACCEPTANCE = PROJECT_ROOT / "public-docs" / "sprint-5-evaluation-baseline.md"
PUBLIC_ROADMAP = PROJECT_ROOT / "public-docs" / "roadmap.md"


def test_sprint5_acceptance_records_content_free_baseline_and_known_gaps() -> None:
    """Locks Sprint 5 acceptance as aggregate/content-free evidence only."""
    assert SPRINT5_ACCEPTANCE.exists()

    text = SPRINT5_ACCEPTANCE.read_text()
    required_terms = (
        "Sprint 5.0 Acceptance",
        "evaluation/bench/cases/public/synthetic-dependency-change.yaml",
        "Cases: 1",
        "Evaluated: 0",
        "Unavailable: 1",
        "Coverage Gaps: 1",
        "Precision: 0.000",
        "Recall: 0.000",
        "Recommendation Agreement: 0.000",
        "scan_adapter_unavailable",
        "Known gaps",
        "Architecture audit: CLEAN",
        "S5.0-14",
    )
    for term in required_terms:
        assert term in text

    _assert_content_free_public_text(text)


def test_public_roadmap_contains_only_aggregate_sprint5_evaluation_status() -> None:
    """Prevents public docs from leaking private benchmark details."""
    text = PUBLIC_ROADMAP.read_text()

    assert "Sprint 5.0 baseline" in text
    assert "public synthetic case" in text
    assert "1 case" in text
    assert "0 evaluated" in text
    assert "1 unavailable" in text
    assert "scan adapter unavailable" in text
    assert "raw private" in text

    _assert_content_free_public_text(text)


def _assert_content_free_public_text(text: str) -> None:
    forbidden_fragments = (
        "diff --git",
        "PRIVATE_RAW_SOURCE",
        "api_key=sk_live",
        "ghp_raw_secret",
        "https://git.linecorp.com",
        "ghe.corp.yahoo.co.jp",
    )
    for forbidden_fragment in forbidden_fragments:
        assert forbidden_fragment not in text
