import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pr_radar.contracts import (
    BlastRadiusBudget,
    BlastRadiusDependent,
    BlastRadiusSummary,
)


@dataclass(frozen=True)
class _PythonImportRef:
    module: str
    import_ref: str


def trace_blast_radius(
    *,
    workspace_path: str | Path,
    changed_paths: Sequence[str],
    max_dependents: int,
) -> BlastRadiusSummary:
    workspace = Path(workspace_path)
    normalized_changed_paths = tuple(
        _normalize_changed_path(workspace, changed_path)
        for changed_path in changed_paths
    )

    if not workspace.exists():
        return _unavailable_summary(
            reason_code="missing_local_workspace",
            changed_paths=normalized_changed_paths,
            max_dependents=max_dependents,
        )

    unsupported_paths = tuple(
        path for path in normalized_changed_paths if not path.endswith(".py")
    )
    if unsupported_paths:
        return _unavailable_summary(
            reason_code="unsupported_python_only_changed_file",
            changed_paths=normalized_changed_paths,
            max_dependents=max_dependents,
        )

    missing_paths = tuple(
        path for path in normalized_changed_paths if not (workspace / path).exists()
    )
    if missing_paths:
        return _unavailable_summary(
            reason_code="missing_changed_file",
            changed_paths=normalized_changed_paths,
            max_dependents=max_dependents,
        )

    changed_modules_by_path = {
        path: _module_candidates_for_path(path) for path in normalized_changed_paths
    }
    changed_module_to_path = {
        module: changed_path
        for changed_path, modules in changed_modules_by_path.items()
        for module in modules
    }
    changed_path_order = {
        changed_path: index
        for index, changed_path in enumerate(normalized_changed_paths)
    }

    dependents = tuple(
        sorted(
            _find_direct_dependents(
                workspace=workspace,
                changed_paths=frozenset(normalized_changed_paths),
                changed_module_to_path=changed_module_to_path,
            ),
            key=lambda dependent: (
                changed_path_order[dependent.changed_path],
                dependent.dependent_path,
                dependent.import_ref,
            ),
        ),
    )
    emitted_dependents = dependents[:max_dependents]
    omitted_dependents = max(0, len(dependents) - len(emitted_dependents))
    truncated = omitted_dependents > 0

    return BlastRadiusSummary(
        availability="partial" if truncated else "available",
        reason_code="budget_truncated" if truncated else "local_workspace_python_imports",
        changed_paths=normalized_changed_paths,
        direct_dependents=emitted_dependents,
        dependent_count=len(dependents),
        budget=BlastRadiusBudget(
            max_dependents=max_dependents,
            emitted_dependents=len(emitted_dependents),
            omitted_dependents=omitted_dependents,
        ),
        truncated=truncated,
    )


def _find_direct_dependents(
    *,
    workspace: Path,
    changed_paths: frozenset[str],
    changed_module_to_path: dict[str, str],
) -> Iterable[BlastRadiusDependent]:
    emitted: set[tuple[str, str, str]] = set()

    for file_path in sorted(workspace.rglob("*.py")):
        dependent_path = _relative_path(workspace, file_path)
        if dependent_path in changed_paths:
            continue
        for import_ref in _parse_python_import_refs(file_path):
            changed_path = _matching_changed_path(
                module=import_ref.module,
                changed_module_to_path=changed_module_to_path,
            )
            if changed_path is None:
                continue
            key = (changed_path, dependent_path, import_ref.import_ref)
            if key in emitted:
                continue
            emitted.add(key)
            yield BlastRadiusDependent(
                changed_path=changed_path,
                dependent_path=dependent_path,
                import_ref=import_ref.import_ref,
            )


def _parse_python_import_refs(file_path: Path) -> tuple[_PythonImportRef, ...]:
    try:
        syntax_tree = ast.parse(file_path.read_text())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ()

    refs: list[_PythonImportRef] = []
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.append(
                    _PythonImportRef(
                        module=alias.name,
                        import_ref=f"import {_format_alias(alias)}",
                    ),
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names = ", ".join(_format_alias(alias) for alias in node.names)
            refs.append(
                _PythonImportRef(
                    module=node.module,
                    import_ref=f"from {node.module} import {imported_names}",
                ),
            )
    return tuple(refs)


def _matching_changed_path(
    *,
    module: str,
    changed_module_to_path: dict[str, str],
) -> str | None:
    for changed_module, changed_path in changed_module_to_path.items():
        if module == changed_module or module.startswith(f"{changed_module}."):
            return changed_path
    return None


def _module_candidates_for_path(path: str) -> tuple[str, ...]:
    without_suffix = path.removesuffix(".py")
    parts = tuple(part for part in without_suffix.split("/") if part)
    if not parts:
        return ()
    if parts[-1] == "__init__":
        parts = parts[:-1]

    candidates = {".".join(parts[index:]) for index in range(len(parts))}
    return tuple(sorted(candidate for candidate in candidates if candidate))


def _format_alias(alias: ast.alias) -> str:
    if alias.asname:
        return f"{alias.name} as {alias.asname}"
    return alias.name


def _normalize_changed_path(workspace: Path, changed_path: str) -> str:
    path = Path(changed_path)
    if path.is_absolute():
        try:
            return path.relative_to(workspace).as_posix()
        except ValueError:
            return path.as_posix().lstrip("/")
    return path.as_posix().lstrip("./")


def _relative_path(workspace: Path, file_path: Path) -> str:
    return file_path.relative_to(workspace).as_posix()


def _unavailable_summary(
    *,
    reason_code: str,
    changed_paths: tuple[str, ...],
    max_dependents: int,
) -> BlastRadiusSummary:
    return BlastRadiusSummary(
        availability="unavailable",
        reason_code=reason_code,
        changed_paths=changed_paths,
        direct_dependents=(),
        dependent_count=0,
        budget=BlastRadiusBudget(
            max_dependents=max_dependents,
            emitted_dependents=0,
            omitted_dependents=0,
        ),
        truncated=False,
    )
