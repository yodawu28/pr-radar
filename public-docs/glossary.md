# Glossary

## AI Risk Assessor

A tool that helps developers decide whether a pull request is safe to approve
or should request changes. PR Radar focuses on security, deployment, blast
radius, performance, anti-bloat, test integrity, and rollback risks.

## Zero Nitpicks

The product principle that style-only or preference-only comments should be
suppressed. Every reported finding must help a developer make a safer merge
decision.

## PR URL

The primary Phase 1 input. A PR URL identifies the pull request to inspect.
GitHub.com and GitHub Enterprise style URLs are supported first.

## Review-Grade Evidence

Evidence rich enough to support risk findings. For PR URL mode this means
fetched PR metadata, commits, changed files, diffs, and file content as needed.
Parser-only URL identity is useful for smoke tests but is not a complete
review.

## Raw Evidence

Private PR data such as raw diffs or source file content. Raw evidence may be
processed locally by deterministic detectors, but it must not be persisted in
reports or sent to hosted services by default.

## Evidence Reference

A report-safe pointer to where evidence came from, such as `pr.title`,
`commit:abc1234`, `file:pyproject.toml`, or `diff:src/service.py`.

## Redacted Excerpt

A short snippet derived from raw evidence after redaction. Redacted excerpts
may appear in reports when they help a developer verify a finding quickly.

## Decision Model Layer

A bounded decision step that can assign status, score, confidence, and report
inclusion decisions from structured evidence. Deterministic static checks remain
the first layer and cannot be overridden by model output.

## Bounded Context Envelope

A compact, report-safe context payload built from stable finding IDs, detector
metadata, evidence references, redacted excerpts, and budget metadata. It avoids
whole-repository dumps and raw PR diffs.

## Low-Confidence Finding

A finding whose evidence is ambiguous but important enough not to suppress.
Low-confidence findings should stay visible so developers can make the final
call.
