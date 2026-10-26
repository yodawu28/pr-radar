from collections.abc import Mapping
from typing import cast

from pr_radar.adapters.github.http import GitHubHttpResponse
from pr_radar.contracts import (
    ChangedFileMetadata,
    CommitMetadata,
    EvidenceReference,
    GitHubChangedFileStatus,
    PrMetadata,
)


def mapping_body(response: GitHubHttpResponse) -> Mapping[str, object]:
    return mapping_body_from_object(response.body)


def mapping_body_from_object(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def sequence_body(response: GitHubHttpResponse) -> tuple[object, ...]:
    if isinstance(response.body, (list, tuple)):
        return tuple(response.body)
    return ()


def text_body(response: GitHubHttpResponse) -> str:
    if isinstance(response.body, str):
        return response.body
    return ""


def pr_metadata(body: Mapping[str, object]) -> PrMetadata:
    user = mapping_body_from_object(body.get("user"))
    head = mapping_body_from_object(body.get("head"))
    base = mapping_body_from_object(body.get("base"))
    return PrMetadata(
        title=_string_value(body.get("title")),
        body=_string_value(body.get("body")),
        author_login=_string_value(user.get("login")),
        head_ref=_string_value(head.get("ref")),
        base_ref=_string_value(base.get("ref")),
        labels=_label_names(body.get("labels")),
    )


def commit(value: object) -> CommitMetadata:
    body = mapping_body_from_object(value)
    author = mapping_body_from_object(body.get("author"))
    committer = mapping_body_from_object(body.get("committer"))
    commit_body = mapping_body_from_object(body.get("commit"))
    return CommitMetadata(
        sha=_string_value(body.get("sha")),
        author_login=_string_value(author.get("login")),
        committer_login=_string_value(committer.get("login")),
        message=_string_value(commit_body.get("message")),
    )


def changed_file(value: object) -> ChangedFileMetadata:
    return _changed_file(value)


def _changed_file(value: object) -> ChangedFileMetadata:
    body = mapping_body_from_object(value)
    return ChangedFileMetadata(
        path=_string_value(body.get("filename")),
        status=_changed_file_status(body.get("status")),
        additions=_int_value(body.get("additions")),
        deletions=_int_value(body.get("deletions")),
    )


def evidence_refs(
    changed_files: tuple[ChangedFileMetadata, ...],
) -> tuple[EvidenceReference, ...]:
    refs = [EvidenceReference(kind="diff", ref="diff:pull")]
    refs.extend(
        EvidenceReference(kind="file", ref=f"file:{changed_file.path}")
        for changed_file in changed_files
    )
    return tuple(refs)


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _label_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()

    names: list[str] = []
    for label in value:
        label_body = mapping_body_from_object(label)
        label_name = label_body.get("name")
        if isinstance(label_name, str):
            names.append(label_name)
    return tuple(names)


def _changed_file_status(value: object) -> GitHubChangedFileStatus:
    if value in {
        "added",
        "modified",
        "removed",
        "renamed",
        "copied",
        "changed",
        "unchanged",
    }:
        return cast(GitHubChangedFileStatus, value)
    return "changed"


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return max(value, 0)
    return 0
