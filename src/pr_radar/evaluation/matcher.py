from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeGuard

from pr_radar.contracts import Finding, LOW_CONFIDENCE_TAG, RADAR_PILLARS, RadarPillarKey
from pr_radar.evaluation.contracts import (
    ExpectedFinding,
    FindingMatchResult,
    MatchOutcome,
)


RuleIdMapping = Mapping[str, tuple[str, str]]

_PRIMARY_MATCH_REASON = "pillar_reason_path_match"
_RULE_ID_MATCH_REASON = "external_rule_id_mapping"
_LOW_CONFIDENCE_MATCH_REASON = "low_confidence_match"
_NO_ACTUAL_MATCH_REASON = "no_actual_match"
_NO_EXPECTED_MATCH_REASON = "no_expected_match"
_DUPLICATE_ACTUAL_MATCH_REASON = "duplicate_actual_match"
_RADAR_PILLAR_KEYS = frozenset(pillar.key for pillar in RADAR_PILLARS)


@dataclass(frozen=True)
class _CandidateMatch:
    expected: ExpectedFinding
    actual: Finding
    match_reason_code: str


def match_findings(
    *,
    expected_findings: Sequence[ExpectedFinding],
    actual_findings: Sequence[Finding],
    rule_id_mapping: RuleIdMapping | None = None,
) -> tuple[FindingMatchResult, ...]:
    """Match expected labels to actual findings through deterministic keys."""
    mapping: RuleIdMapping = rule_id_mapping or {}
    matched_expected_ids: set[str] = set()
    matched_actual_ids: set[str] = set()
    duplicate_actual_ids: set[str] = set()
    matched_results: list[FindingMatchResult] = []
    results: list[FindingMatchResult] = []

    for expected in sorted(expected_findings, key=_expected_sort_key):
        candidates = tuple(
            candidate
            for candidate in _candidate_matches(expected, actual_findings, mapping)
            if candidate.actual.id not in matched_actual_ids
        )
        if not candidates:
            continue

        selected = _best_candidate(candidates)
        matched_expected_ids.add(expected.finding_id)
        matched_actual_ids.add(selected.actual.id)
        matched_results.append(_matched_result(selected))

        for duplicate in candidates:
            if duplicate.actual.id == selected.actual.id:
                continue
            duplicate_actual_ids.add(duplicate.actual.id)
            matched_actual_ids.add(duplicate.actual.id)
            matched_results.append(
                _unexpected_actual_result(
                    duplicate.actual,
                    match_reason_code=_DUPLICATE_ACTUAL_MATCH_REASON,
                ),
            )

    results.extend(sorted(matched_results, key=_result_sort_key))

    for expected in sorted(expected_findings, key=_expected_sort_key):
        if expected.finding_id in matched_expected_ids:
            continue
        results.append(_missing_expected_result(expected))

    for actual in sorted(actual_findings, key=_actual_sort_key):
        if actual.id in matched_actual_ids or actual.id in duplicate_actual_ids:
            continue
        results.append(
            _unexpected_actual_result(
                actual,
                match_reason_code=_NO_EXPECTED_MATCH_REASON,
            ),
        )

    return tuple(results)


def _candidate_matches(
    expected: ExpectedFinding,
    actual_findings: Sequence[Finding],
    rule_id_mapping: RuleIdMapping,
) -> tuple[_CandidateMatch, ...]:
    candidates = [
        _CandidateMatch(
            expected=expected,
            actual=actual,
            match_reason_code=_PRIMARY_MATCH_REASON,
        )
        for actual in actual_findings
        if _matches_expected(
            expected=expected,
            actual=actual,
            pillar=expected.pillar,
            reason_code=expected.reason_code,
        )
    ]
    if candidates:
        return tuple(candidates)

    mapped_key = _mapped_expected_key(expected, rule_id_mapping)
    if mapped_key is None:
        return ()
    mapped_pillar, mapped_reason_code = mapped_key
    return tuple(
        _CandidateMatch(
            expected=expected,
            actual=actual,
            match_reason_code=_RULE_ID_MATCH_REASON,
        )
        for actual in actual_findings
        if _matches_expected(
            expected=expected,
            actual=actual,
            pillar=_radar_pillar(mapped_pillar),
            reason_code=mapped_reason_code,
        )
    )


def _matches_expected(
    *,
    expected: ExpectedFinding,
    actual: Finding,
    pillar: RadarPillarKey,
    reason_code: str,
) -> bool:
    return (
        actual.pillar == pillar
        and actual.calibration_reason == reason_code
        and _has_evidence_path(actual, expected.evidence_path)
    )


def _mapped_expected_key(
    expected: ExpectedFinding,
    rule_id_mapping: RuleIdMapping,
) -> tuple[str, str] | None:
    if expected.source_rule_id is None:
        return None
    return rule_id_mapping.get(expected.source_rule_id)


def _best_candidate(candidates: Sequence[_CandidateMatch]) -> _CandidateMatch:
    return sorted(candidates, key=lambda candidate: _actual_sort_key(candidate.actual))[0]


def _matched_result(candidate: _CandidateMatch) -> FindingMatchResult:
    outcome: MatchOutcome = (
        "low_confidence_match"
        if _is_low_confidence(candidate.actual)
        else "matched_expected"
    )
    match_reason_code = (
        _LOW_CONFIDENCE_MATCH_REASON
        if outcome == "low_confidence_match"
        else candidate.match_reason_code
    )
    return FindingMatchResult(
        outcome=outcome,
        expected_finding_id=candidate.expected.finding_id,
        actual_finding_id=candidate.actual.id,
        pillar=_actual_pillar(candidate.actual),
        reason_code=candidate.actual.calibration_reason
        or candidate.expected.reason_code,
        evidence_path=candidate.expected.evidence_path,
        match_reason_code=match_reason_code,
    )


def _missing_expected_result(expected: ExpectedFinding) -> FindingMatchResult:
    return FindingMatchResult(
        outcome="missing_expected",
        expected_finding_id=expected.finding_id,
        pillar=expected.pillar,
        reason_code=expected.reason_code,
        evidence_path=expected.evidence_path,
        match_reason_code=_NO_ACTUAL_MATCH_REASON,
    )


def _unexpected_actual_result(
    actual: Finding,
    *,
    match_reason_code: str,
) -> FindingMatchResult:
    return FindingMatchResult(
        outcome="unexpected_actual",
        actual_finding_id=actual.id,
        pillar=_actual_pillar(actual),
        reason_code=actual.calibration_reason or actual.id,
        evidence_path=_first_file_evidence_path(actual),
        match_reason_code=match_reason_code,
    )


def _has_evidence_path(actual: Finding, evidence_path: str) -> bool:
    return any(
        evidence_ref in {f"file:{evidence_path}", f"diff:{evidence_path}"}
        for evidence_ref in actual.evidence_refs
    )


def _first_file_evidence_path(actual: Finding) -> str | None:
    for evidence_ref in actual.evidence_refs:
        if evidence_ref.startswith("file:"):
            return evidence_ref.removeprefix("file:")
    return None


def _is_low_confidence(actual: Finding) -> bool:
    return LOW_CONFIDENCE_TAG in actual.tags


def _actual_pillar(actual: Finding) -> RadarPillarKey:
    return _radar_pillar(actual.pillar)


def _radar_pillar(value: str) -> RadarPillarKey:
    if _is_radar_pillar(value):
        return value
    raise ValueError(f"unknown radar pillar: {value}")


def _is_radar_pillar(value: str) -> TypeGuard[RadarPillarKey]:
    return value in _RADAR_PILLAR_KEYS


def _expected_sort_key(expected: ExpectedFinding) -> tuple[str, str, str]:
    return (expected.pillar, expected.reason_code, expected.finding_id)


def _actual_sort_key(actual: Finding) -> tuple[int, int, str]:
    return (-actual.score, -round(actual.confidence * 1000), actual.id)


def _result_sort_key(result: FindingMatchResult) -> tuple[str, str]:
    return (result.actual_finding_id or "", result.expected_finding_id or "")
