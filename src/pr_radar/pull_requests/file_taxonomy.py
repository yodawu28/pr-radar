from typing import Literal, TypeAlias


DependencyManifestKind: TypeAlias = Literal["pyproject", "package_json"]

_SOURCE_EXTENSIONS = (
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
)
_TEST_PATH_PARTS = (
    "/test_",
    "/tests/",
    "_test.",
    ".test.",
    ".spec.",
)


def dependency_manifest_kind(path: str) -> DependencyManifestKind | None:
    normalized_path = path.strip("/").lower()
    if normalized_path == "pyproject.toml" or normalized_path.endswith(
        "/pyproject.toml",
    ):
        return "pyproject"
    if normalized_path == "package.json" or normalized_path.endswith("/package.json"):
        return "package_json"
    return None


def is_sql_migration(path: str) -> bool:
    normalized_path = path.lower()
    return normalized_path.endswith(".sql") and "migration" in normalized_path


def is_test_path(path: str) -> bool:
    normalized_path = f"/{path.strip('/').lower()}"
    return any(part in normalized_path for part in _TEST_PATH_PARTS)


def is_source_path(path: str) -> bool:
    return path.lower().endswith(_SOURCE_EXTENSIONS)
