import ast
from collections.abc import Iterable
from importlib.util import find_spec
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "pr_radar"

TARGET_PACKAGES = (
    "pr_radar.application",
    "pr_radar.pull_requests",
    "pr_radar.privacy",
    "pr_radar.review",
    "pr_radar.reporting",
)

ROOT_FACADES = {
    "src/pr_radar/scan.py": "pr_radar.application.scan",
    "src/pr_radar/pr_urls.py": "pr_radar.pull_requests.identity",
    "src/pr_radar/redaction.py": "pr_radar.privacy.redaction",
    "src/pr_radar/report_renderer.py": "pr_radar.reporting.text",
}


def test_workflow_domain_target_packages_exist() -> None:
    """Catches ADR-014 target packages not being created before migration."""
    missing_packages = tuple(
        package for package in TARGET_PACKAGES if find_spec(package) is None
    )

    assert missing_packages == ()


def test_review_package_owns_decision_behavior_without_detector_imports() -> None:
    """Catches decision-domain code drifting into detectors or scan facades."""
    assert (SRC_ROOT / "review").exists()

    review_imports = {
        imported
        for path in sorted(SRC_ROOT.joinpath("review").rglob("*.py"))
        for imported in _module_imports(path)
    }

    assert not {
        imported
        for imported in review_imports
        if imported.startswith("pr_radar.detectors")
    }
    assert not {
        imported
        for imported in review_imports
        if imported.startswith("pr_radar.application")
    }


def test_root_workflow_modules_are_thin_compatibility_facades() -> None:
    """Catches domain logic drifting back into root compatibility modules."""
    violations = {}
    for relative_path, target_module in ROOT_FACADES.items():
        syntax_tree = _module_syntax_tree(relative_path)
        definitions = _top_level_definitions(syntax_tree)
        imported_modules = _imported_modules(syntax_tree)
        if definitions or imported_modules != {target_module}:
            violations[relative_path] = {
                "definitions": definitions,
                "imported_modules": sorted(imported_modules),
                "expected_import": target_module,
            }

    assert violations == {}


def test_pr_radar_source_modules_do_not_have_import_cycles() -> None:
    """Catches package-boundary refactors that make modules import each other in loops."""
    graph = _local_import_graph()
    cycles = tuple(_find_cycles(graph))

    assert cycles == ()


def test_scan_uses_contract_context_envelope_type_not_application_reexport() -> None:
    """Catches static analyzer drift from importing contract models via builders."""
    syntax_tree = _module_syntax_tree("src/pr_radar/application/scan.py")
    imported_names = {
        (node.module, alias.name)
        for node in syntax_tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
        for alias in node.names
    }

    assert ("pr_radar.contracts", "ContextEnvelope") in imported_names
    assert ("pr_radar.application.context", "ContextEnvelope") not in imported_names


def test_detector_families_are_grouped_by_radar_pillar() -> None:
    """Catches detector implementation modules drifting back into a flat bucket."""
    target_packages = (
        "pr_radar.detectors.security_supply_chain",
        "pr_radar.detectors.deployment_downtime",
        "pr_radar.detectors.test_integrity",
        "pr_radar.detectors._shared",
    )
    missing_packages = tuple(
        package for package in target_packages if find_spec(package) is None
    )
    flat_implementations = tuple(
        path.name
        for path in sorted(SRC_ROOT.joinpath("detectors").glob("*.py"))
        if path.name
        not in {
            "__init__.py",
            "ai_signal.py",
            "static_risk.py",
        }
    )

    assert missing_packages == ()
    assert flat_implementations == ()


def test_public_documentation_surface_is_available() -> None:
    """Catches publishing a repo without the public docs entry points."""
    readme = (PROJECT_ROOT / "README.md").read_text()
    public_docs = (PROJECT_ROOT / "public-docs" / "README.md").read_text()
    roadmap = (PROJECT_ROOT / "public-docs" / "roadmap.md").read_text()

    assert "Privacy-first AI risk radar" in readme
    assert "Decision Recommendation" in readme
    assert "Product roadmap" in public_docs
    assert "Phase 1: Local Utility And Core Risk Engine" in roadmap
    assert "local decision recommendations" in roadmap


def test_internal_docs_are_not_required_by_public_contract_tests() -> None:
    """Catches reintroducing internal docs as required public test fixtures."""
    test_source = Path(__file__).read_text()
    internal_docs_join = "/ " + '"docs"'
    internal_prd_name = "prd_ai" + "_code_review_radar"

    assert internal_docs_join not in test_source
    assert internal_prd_name not in test_source


def _module_syntax_tree(relative_path: str) -> ast.Module:
    return ast.parse((PROJECT_ROOT / relative_path).read_text())


def _top_level_definitions(syntax_tree: ast.Module) -> tuple[str, ...]:
    return tuple(
        node.name
        for node in syntax_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    )


def _imported_modules(syntax_tree: ast.Module) -> set[str]:
    return {
        node.module
        for node in syntax_tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def _local_import_graph() -> dict[str, set[str]]:
    modules = {_module_name(path) for path in SRC_ROOT.rglob("*.py")}
    graph: dict[str, set[str]] = {module: set() for module in modules}
    for path in SRC_ROOT.rglob("*.py"):
        module = _module_name(path)
        imports = _module_imports(path)
        graph[module] = {imported for imported in imports if imported in modules}
    return graph


def _module_name(path: Path) -> str:
    relative_path = path.relative_to(PROJECT_ROOT / "src").with_suffix("")
    return ".".join(relative_path.parts)


def _module_imports(path: Path) -> set[str]:
    syntax_tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return {
        imported
        for imported in imports
        if imported == "pr_radar" or imported.startswith("pr_radar.")
    }


def _find_cycles(graph: dict[str, set[str]]) -> Iterable[tuple[str, ...]]:
    visited: set[str] = set()
    active_stack: list[str] = []
    active_set: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(module: str) -> None:
        if module in active_set:
            cycle_start = active_stack.index(module)
            cycles.add(tuple(active_stack[cycle_start:] + [module]))
            return
        if module in visited:
            return

        visited.add(module)
        active_stack.append(module)
        active_set.add(module)
        for imported_module in sorted(graph[module]):
            visit(imported_module)
        active_stack.pop()
        active_set.remove(module)

    for module in sorted(graph):
        visit(module)

    return tuple(sorted(cycles))
