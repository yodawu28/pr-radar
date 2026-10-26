# PR Radar Product Roadmap

PR Radar is a privacy-first AI Risk Assessor and Decision Radar for pull
requests. It focuses on deterministic checks, bounded context, and
evidence-backed local reports instead of noisy inline review comments.

## Phase 1: Local Utility And Core Risk Engine

Scope: Sprint 1.0 through Sprint 3.1.

Goals:
- Provide a local CLI for GitHub.com and GitHub Enterprise PR URLs.
- Fetch PR evidence safely when the user provides credentials.
- Detect AI-generation signals from PR metadata and repository markers.
- Run the first deterministic risk detectors:
  dependency additions, destructive migration clues, and test-shape risks.
- Build a bounded context envelope for future decision-layer use.

Non-goals:
- No hosted service requirement.
- No automatic merge approval.
- No raw private diff or source upload by default.

## Phase 2: Decision Layer And Local Evaluation

Scope: Sprint 4.0 through Sprint 5.0.

Goals:
- Add a Kev/local decision layer over bounded context.
- Score severity and report inclusion without overriding deterministic failures.
- Preserve low-confidence findings in the report.
- Evaluate findings against curated ground-truth repositories by finding ID.

## Phase 3: Team Integration And GitHub Automation

Scope: Sprint 6.0 and later.

Goals:
- Prepare GitHub Action or webhook automation.
- Publish one executive summary comment per PR.
- Add configurable policy mapping for team or organization use.
- Keep developers in control of final merge decisions.
