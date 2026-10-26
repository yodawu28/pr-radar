import ast
from pathlib import Path
from typing import get_args

import pytest

from pr_radar.pr_urls import PrUrlParseError, _deployment_for_host, parse_pr_url


def test_parse_github_pr_url_into_pr_input() -> None:
    """Catches parsers that do not extract GitHub PR identity."""
    pr_input = parse_pr_url("https://github.com/example/repo/pull/17")

    assert pr_input.provider == "github"
    assert pr_input.deployment == "github_com"
    assert pr_input.repository == "example/repo"
    assert pr_input.pull_request_number == 17
    assert pr_input.url == "https://github.com/example/repo/pull/17"


def test_parse_github_enterprise_style_url_and_normalizes_noise() -> None:
    """Catches parsers that reject GitHub-compatible enterprise hosts."""
    pr_input = parse_pr_url(
        "https://git.example.internal/team/repo/pull/42/files?plain=1#discussion",
    )

    assert pr_input.provider == "github"
    assert pr_input.deployment == "github_self_hosted"
    assert pr_input.repository == "team/repo"
    assert pr_input.pull_request_number == 42
    assert pr_input.url == "https://git.example.internal/team/repo/pull/42"


def test_parse_github_self_hosted_url_without_host_in_repository() -> None:
    """Catches parsers that fold enterprise hostnames into repository identity."""
    pr_input = parse_pr_url(
        "https://git.linecorp.com/arkdevelopers/code-review-agent/pull/59",
    )

    assert pr_input.provider == "github"
    assert pr_input.deployment == "github_self_hosted"
    assert pr_input.repository == "arkdevelopers/code-review-agent"
    assert pr_input.pull_request_number == 59
    assert (
        pr_input.url
        == "https://git.linecorp.com/arkdevelopers/code-review-agent/pull/59"
    )


def test_pr_url_parser_imports_contracts_from_public_facade() -> None:
    """Catches parser code bypassing the stable contract facade."""
    module_path = (
        Path(__file__).parents[1]
        / "src"
        / "pr_radar"
        / "pull_requests"
        / "identity.py"
    )
    syntax_tree = ast.parse(module_path.read_text())

    import_sources = {
        node.module
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in {"PrDeployment", "PrInput"}
    }

    assert import_sources == {"pr_radar.contracts"}


def test_deployment_helper_return_type_stays_narrow_for_pr_input_contract() -> None:
    """Catches widening deployment helper output to arbitrary str."""
    assert set(get_args(_deployment_for_host.__annotations__["return"])) == {
        "github_com",
        "github_self_hosted",
    }


@pytest.mark.parametrize(
    ("url", "expected_reason"),
    [
        ("not a url", "absolute URL"),
        ("https://github.com/example/repo/issues/17", "pull request path"),
        ("https://github.com/example/repo/pull/", "pull request number"),
        ("https://gitlab.com/example/repo/-/merge_requests/17", "unsupported"),
        ("https://token@github.com/example/repo/pull/17", "credentials"),
    ],
)
def test_parse_pr_url_fails_closed_for_invalid_inputs(
    url: str,
    expected_reason: str,
) -> None:
    """Catches parsers that silently accept non-PR or unsupported URLs."""
    with pytest.raises(PrUrlParseError, match=expected_reason):
        parse_pr_url(url)
