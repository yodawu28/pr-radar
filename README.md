```text
   _____  ____     ____            __
  / ___ \/ __ \   / __ \____ _____/ /___ ______
 / /_/ / /_/ /  / /_/ / __ `/ __  / __ `/ ___/
/ ____/ _, _/  / _, _/ /_/ / /_/ / /_/ / /
/_/   /_/ |_|  /_/ |_|\__,_/\__,_/\__,_/_/

        Privacy-first PR risk radar
```

# PR Radar

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![uv](https://img.shields.io/badge/package%20manager-uv-4B32C3)
![Status](https://img.shields.io/badge/status-Phase%201-blue)
![Privacy](https://img.shields.io/badge/privacy-local--first-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

Privacy-first AI risk radar for pull requests, helping developers review
AI-generated or AI-assisted code with deterministic checks and evidence-backed
reports.

PR Radar is not a nitpick bot. It compresses pull request context into a local
risk report so a developer can decide whether a PR is safe to approve or needs
changes.

## Status

PR Radar is in Phase 1: local CLI and core deterministic risk engine.

Current capabilities:
- Parse GitHub.com and GitHub Enterprise pull request URLs.
- Fetch review-grade PR evidence when credentials are provided.
- Detect AI-generation signals from metadata, branch names, PR text, and repo
  marker files.
- Run deterministic detectors for dependency additions, destructive migration
  clues, and test-shape risks.
- Render a local text report with stable finding IDs, evidence references,
  calibration reasons, and redacted excerpts.
- Build a bounded context envelope for future decision-layer use.

## Quickstart

```bash
uv sync
./scripts/verify.sh
uv run pr-radar scan https://github.com/OWNER/REPO/pull/123
```

For private repositories or GitHub Enterprise, configure credentials with
environment variables. See [.env.example](.env.example).

```bash
GITHUB_TOKEN=ghp_example uv run pr-radar scan \
  https://github.com/OWNER/REPO/pull/123 \
  --fetch-evidence
```

```bash
GHE_TOKEN=ghp_enterprise_example uv run pr-radar scan \
  https://ghe.example.com/OWNER/REPO/pull/123 \
  --fetch-evidence
```

## Privacy Model

PR Radar processes raw PR diffs and source content locally by default. Reports
and context envelopes must not persist raw private source, full diffs, secrets,
credentials, or PII. Human-readable output may include only normalized evidence
references and short redacted excerpts.

Hosted LLM or hosted decision-model calls are future opt-in behavior and must
require explicit user configuration.

## Public Docs

- [Product roadmap](public-docs/roadmap.md)
- [Glossary](public-docs/glossary.md)

Internal planning and harness files are kept outside the public documentation
surface.

## Development

```bash
uv sync
./scripts/verify.sh
```

The verifier runs the pytest suite and CLI smoke checks. When local harness
files are present, it also validates the harness context files.

## License

MIT License. See [LICENSE](LICENSE).
