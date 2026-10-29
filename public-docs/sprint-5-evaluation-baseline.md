# Sprint 5.0 Acceptance: Evaluation Baseline

Date: 2026-10-29

Task: S5.0-14

## Baseline Command

```bash
uv run pr-radar eval evaluation/bench/cases/public/synthetic-dependency-change.yaml --output-dir evaluation/outputs/sprint-5-baseline
```

Generated artifacts are under `evaluation/outputs/`, which is ignored by git.
This public baseline records only content-free aggregate metrics.

## Content-Free Baseline

Source manifest:
`evaluation/bench/cases/public/synthetic-dependency-change.yaml`

Summary:
- Cases: 1
- Evaluated: 0
- Unavailable: 1
- Invalid: 0
- Precision: 0.000
- Recall: 0.000
- Recommendation Agreement: 0.000
- Coverage Gaps: 1

Coverage gaps by reason:
- `scan_adapter_unavailable`: 1

## Known gaps

- The Sprint 5 CLI evaluation path can load manifests and write content-free
  artifacts, but it does not yet have a real scan adapter for replay/source
  present cases. This is why the public synthetic case is counted as
  unavailable instead of evaluated.
- No strict quality gate is introduced in Sprint 5.0. The baseline is a
  measurement checkpoint for deciding whether later Sprint 5.5 Kev/model lab,
  RAG, VectorDB, Knowledge Graph, or context-provider work is justified.
- Private ground-truth repositories and detailed benchmark outputs remain
  internal-only and are not represented in this public-safe baseline.

## Architecture audit

Architecture audit: CLEAN

Evidence:
- `uv run pytest tests/test_package_boundaries.py -q` passed with 13 tests.
- Runtime scan/review paths do not import `pr_radar.evaluation`.
- Evaluation outputs remain under ignored generated-output paths.
