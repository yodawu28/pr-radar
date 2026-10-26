import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify.sh"
AGENTS_GUIDE = PROJECT_ROOT / "AGENTS.md"


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


def _shell_constant(script: str, name: str) -> int:
    matches = re.findall(rf"^{name}=(\d+)$", script, flags=re.MULTILINE)

    assert len(matches) == 1
    return int(matches[0])
