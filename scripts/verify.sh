#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf 'VERIFY FAILED: %s\n' "$1" >&2
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "missing required file: $path"
}

require_contains() {
  local path="$1"
  local pattern="$2"
  rg -q "$pattern" "$path" || fail "$path missing required pattern: $pattern"
}

MAX_AGENTS_LINES=150
MAX_PROGRESS_LINES=250

require_file "README.md"
require_file "LICENSE"
require_file "public-docs/README.md"
require_file "public-docs/roadmap.md"
require_file "public-docs/glossary.md"

[[ -x "scripts/verify.sh" ]] || fail "scripts/verify.sh must be executable"

require_contains "README.md" "Privacy-first AI risk radar"
require_contains "README.md" "license-MIT"
require_contains "README.md" "uv sync"
require_contains "LICENSE" "MIT License"
require_contains "public-docs/roadmap.md" "Phase 1"
require_contains "public-docs/glossary.md" "Decision Model Layer"

if [[ -f "AGENTS.md" && -f "PROGRESS.md" && -f "DECISIONS.md" ]]; then
  require_contains "AGENTS.md" "scripts/verify\\.sh"
  require_contains "AGENTS.md" "Non-Goals"
  require_contains "AGENTS.md" "Execution Policy"
  require_contains "AGENTS.md" "Agent Skill Shortcuts Registry"
  require_contains "PROGRESS.md" "Current State"
  require_contains "PROGRESS.md" "Next Steps"
  require_contains "DECISIONS.md" "ADR-001"
  require_contains "DECISIONS.md" "ADR-002"
  require_contains "DECISIONS.md" "ADR-003"
  require_contains "DECISIONS.md" "ADR-004"

  AGENTS_LINES="$(wc -l < AGENTS.md | tr -d ' ')"
  [[ "$AGENTS_LINES" -le "$MAX_AGENTS_LINES" ]] || fail "AGENTS.md must stay under $MAX_AGENTS_LINES lines; found $AGENTS_LINES"
fi

bash -n "scripts/verify.sh"

require_file "pyproject.toml"
require_contains "pyproject.toml" "license = \"MIT\""
require_contains "pyproject.toml" "requires-python = \">=3\\.11\""
require_contains "pyproject.toml" "pr-radar = \"pr_radar\\.cli:app\""

uv run pytest
uv run pr-radar --help >/dev/null
uv run pr-radar scan "https://github.com/example/repo/pull/1" >/dev/null

if find . -path ./.git -prune -o -path ./.agents -prune -o -path ./.venv -prune -o -path ./.pytest_cache -prune -o -name '*.md' -print | xargs rg -n $'\t' >/tmp/pr-radar-tabs.txt; then
  cat /tmp/pr-radar-tabs.txt >&2
  fail "markdown files must not contain tab characters"
fi

if [[ -f "PROGRESS.md" ]]; then
  PROGRESS_LINES=$(wc -l < PROGRESS.md)
  if [ "$PROGRESS_LINES" -gt "$MAX_PROGRESS_LINES" ]; then
    fail "[CONTEXT_ERROR] PROGRESS.md exceeded $MAX_PROGRESS_LINES lines (Current: $PROGRESS_LINES). Run 'h-archive' now."
  fi
fi

printf 'Context size within healthy thresholds.\n'
printf 'VERIFY PASSED: harness context is consistent.\n'
