from importlib import import_module, util


def _taxonomy_module():
    assert util.find_spec("pr_radar.pull_requests.file_taxonomy") is not None, (
        "expected shared PR file taxonomy under pr_radar.pull_requests"
    )
    return import_module("pr_radar.pull_requests.file_taxonomy")


def test_file_taxonomy_classifies_dependency_manifests() -> None:
    """Keeps manifest path rules reusable outside detector internals."""
    taxonomy = _taxonomy_module()

    assert taxonomy.dependency_manifest_kind("pyproject.toml") == "pyproject"
    assert taxonomy.dependency_manifest_kind("services/web/package.json") == (
        "package_json"
    )
    assert taxonomy.dependency_manifest_kind("src/package.py") is None


def test_file_taxonomy_classifies_migrations_tests_and_source_files() -> None:
    """Locks the shared path categories needed by detectors and future context."""
    taxonomy = _taxonomy_module()

    assert taxonomy.is_sql_migration("db/migrations/20261026_drop_users.sql")
    assert not taxonomy.is_sql_migration("db/schema.sql")

    assert taxonomy.is_test_path("tests/test_payments.py")
    assert taxonomy.is_test_path("src/payments/service.test.ts")
    assert not taxonomy.is_test_path("src/payments/service.py")

    assert taxonomy.is_source_path("src/payments/service.py")
    assert taxonomy.is_source_path("web/app/checkout.tsx")
    assert not taxonomy.is_source_path("README.md")
