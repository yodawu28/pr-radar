# Public Evaluation Case Schema

Public benchmark cases are synthetic, content-free manifests that can be
synced to the public repository. They document PR Radar evaluation contracts
without copying private Aimigo fixtures, raw source, raw patch content, PR
bodies, credentials, or internal repository metadata.

## Manifest Shape

Public manifests use YAML or JSONL and contain a top-level `cases` list.

- `case_id`: stable synthetic case identifier.
- `source_format`: source adapter label such as `synthetic_replay`.
- `pr_id`: synthetic PR reference only.
- `stack`: optional language or framework label.
- `ruleset_version`: synthetic ruleset version label.
- `labels`: optional normalized tags.
- `source_refs`: content hashes in `path:sha256:<hash>` form.
- `expected_findings`: expected PR Radar findings for the case.

Each `expected_findings` item uses:

- `finding_id`: stable expected finding identifier.
- `pillar`: PR Radar pillar such as `security_supply_chain`.
- `reason_code`: stable reason vocabulary used by matching.
- `evidence_path`: normalized relative path only.
- `severity`: one of `high_risk`, `warning`, or `advisory`.
- `source_rule_id`: optional external rule mapping identifier.
- `source_line`: optional 1-based line number.
- `source_excerpt_hash`: content hash only, never excerpt text.

## Public Content Rules

- Use content-free hashes, normalized labels, relative paths, and stable IDs.
- Use synthetic values for `pr_id`, `labels`, `ruleset_version`, and rule IDs.
- no raw diff content.
- no internal URLs.
- Do not add `patch.diff`, `ground_truth.json`, `PR_BODY`, or `PR_TITLE` files
  under this public directory.
- Private cases belong under `evaluation/bench/cases/private/`.
- Generated outputs belong under `evaluation/outputs/`.
