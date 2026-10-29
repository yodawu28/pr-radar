# Evaluation Bench Cases

Sprint 5 evaluation adapts existing Aimigo benchmark repositories as an
external source format. Do not copy proprietary cases from those repositories
into this repository unless the case is synthetic or explicitly approved for
public release.

## Source Layout

An external Aimigo case directory is expected to look like this:

```text
bench/cases/<case-id>/
  ground_truth.json
  patch.diff
  PR_TITLE or PR_TITLE.txt
  PR_BODY, PR_BODY.md, or PR_BODY.txt
```

`ground_truth.json` is the metadata source of truth. The observed template uses
top-level fields such as `pr_id`, `stack`, `ruleset_version`, `labels`, and
`issues`. Each issue may include `ruleId`, `severity`, `file`, `line`, `title`,
`detail`, `evidence`, `explanation`, `suggestion`, and `references`.

The format is allowed to be partial while benchmark data is being repaired.
Missing optional fields must be represented as partial or unavailable metadata;
the evaluator must not guess missing `ruleId`, `stack`, `title`, `evidence`, or
ruleset values.

## Privacy Boundary

`patch.diff`, PR title files, and PR body files are raw local input. Evaluation
may read them from a local workspace, but generated artifacts and public sync
outputs must not store raw private diffs, raw source, secrets, credentials, PII,
or internal URLs.

Public synthetic cases may live under `evaluation/bench/cases/public/`. Private
or proprietary cases belong under `evaluation/bench/cases/private/`, which is
ignored by git and must not be synced to the public repository.

Generated benchmark outputs belong under `evaluation/outputs/`, which is also
ignored by git. Publish only aggregate, redacted, content-free metrics.

## Severity Normalization

Initial severity normalization is intentionally explicit:

- `critical/high/error`: high-risk expected outcome.
- `medium/warn/warning`: warning expected outcome.
- `low/info/success`: advisory or non-blocking expected outcome.

Rule mapping should prefer an explicit `ruleId` table into PR Radar
pillar/reason vocabulary. Audited prefix fallback is allowed only for unmapped
families.
