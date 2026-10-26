import ast
from pathlib import Path

import pytest

from pr_radar.contracts import PrInput, Report
from pr_radar.adapters.github.mapper import changed_file
from pr_radar.github_adapter import (
    GitHubAuthResolutionError,
    resolve_github_api_plan,
)
from pr_radar.report_renderer import render_text_report


def _module_syntax_tree(relative_path: str) -> ast.Module:
    module_path = Path(__file__).parents[1] / relative_path
    return ast.parse(module_path.read_text())


def _github_com_pr_input() -> PrInput:
    return PrInput(
        provider="github",
        deployment="github_com",
        repository="example/repo",
        pull_request_number=17,
        url="https://github.com/example/repo/pull/17",
    )


def _self_hosted_pr_input(host: str = "git.linecorp.com") -> PrInput:
    return PrInput(
        provider="github",
        deployment="github_self_hosted",
        repository="arkdevelopers/code-review-agent",
        pull_request_number=59,
        url=f"https://{host}/arkdevelopers/code-review-agent/pull/59",
    )


def test_github_adapter_type_aliases_are_explicit_for_static_analyzers() -> None:
    """Catches Pylance/Pyright self-dependency errors from implicit aliases."""
    syntax_tree = _module_syntax_tree("src/pr_radar/adapters/github/auth.py")

    alias_annotations = {
        node.target.id: node.annotation.id
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.annotation, ast.Name)
    }

    assert alias_annotations["DefaultGitHubAuthEnvVar"] == "TypeAlias"


def test_github_adapter_uses_typed_changed_file_status_helper() -> None:
    """Catches Pylance/Pyright Literal drift in ChangedFileMetadata.status."""
    syntax_tree = _module_syntax_tree("src/pr_radar/adapters/github/mapper.py")

    contract_import_names = {
        alias.name
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "pr_radar.contracts"
        for alias in node.names
    }
    changed_file_function = next(
        node
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_changed_file"
    )
    status_keywords = [
        keyword
        for node in ast.walk(changed_file_function)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "status"
    ]

    assert "GitHubChangedFileStatus" in contract_import_names
    assert len(status_keywords) == 1
    assert isinstance(status_keywords[0].value, ast.Call)
    assert isinstance(status_keywords[0].value.func, ast.Name)
    assert status_keywords[0].value.func.id == "_changed_file_status"


def test_github_file_mapper_preserves_github_status_vocabulary() -> None:
    """Catches accidental Git-native translation of GitHub PR file statuses."""
    removed_file = changed_file(
        {
            "filename": "src/old.py",
            "status": "removed",
            "additions": 0,
            "deletions": 12,
        },
    )
    unknown_file = changed_file(
        {
            "filename": "src/odd.py",
            "status": "deleted",
            "additions": 0,
            "deletions": 1,
        },
    )

    assert removed_file.status == "removed"
    assert removed_file.model_dump()["status"] == "removed"
    assert unknown_file.status == "changed"


def test_github_adapter_facade_delegates_to_adapter_package() -> None:
    """Catches provider logic drifting back into the legacy facade module."""
    syntax_tree = _module_syntax_tree("src/pr_radar/github_adapter.py")
    facade_definitions = {
        node.name
        for node in syntax_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    imported_modules = {
        node.module
        for node in syntax_tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert facade_definitions == set()
    assert "pr_radar.adapters.github" in imported_modules


def test_github_com_deployment_uses_github_token_and_public_api_base() -> None:
    """Catches adapters that use enterprise auth defaults for github.com."""
    token = "ghp_public_unit_secret"

    plan = resolve_github_api_plan(
        _github_com_pr_input(),
        env={"GITHUB_TOKEN": token, "GHE_TOKEN": "wrong-enterprise-token"},
    )

    assert plan.api_base_url == "https://api.github.com"
    assert plan.auth_env_var == "GITHUB_TOKEN"
    assert plan.token == token


def test_self_hosted_deployment_uses_ghe_token_and_enterprise_api_base() -> None:
    """Catches adapters that hardcode api.github.com for enterprise hosts."""
    token = "ghe_enterprise_unit_secret"

    plan = resolve_github_api_plan(
        _self_hosted_pr_input("ghe.corp.yahoo.co.jp"),
        env={"GITHUB_TOKEN": "wrong-public-token", "GHE_TOKEN": token},
    )

    assert plan.api_base_url == "https://ghe.corp.yahoo.co.jp/api/v3"
    assert plan.auth_env_var == "GHE_TOKEN"
    assert plan.token == token


def test_self_hosted_deployment_does_not_use_host_specific_tokens_in_sprint_2() -> None:
    """Catches accidental host-specific token mapping before the product needs it."""
    host_specific_token = "host_specific_secret_value"

    with pytest.raises(GitHubAuthResolutionError) as caught:
        resolve_github_api_plan(
            _self_hosted_pr_input("git.linecorp.com"),
            env={"GIT_LINECORP_COM_TOKEN": host_specific_token},
        )

    failure = caught.value.failure
    serialized_failure = failure.model_dump_json()
    assert failure.reason == "missing_token"
    assert "GHE_TOKEN" in failure.message
    assert "GIT_LINECORP_COM_TOKEN" not in serialized_failure
    assert host_specific_token not in str(caught.value)
    assert host_specific_token not in repr(caught.value)
    assert host_specific_token not in serialized_failure


def test_missing_token_error_and_report_safe_message_do_not_leak_env_values() -> None:
    """Catches auth errors that echo raw tokens into errors or local reports."""
    unrelated_token = "ghe_unrelated_secret_value"
    pr_input = _github_com_pr_input()

    with pytest.raises(GitHubAuthResolutionError) as caught:
        resolve_github_api_plan(pr_input, env={"GHE_TOKEN": unrelated_token})

    failure = caught.value.failure
    report = Report(
        overall_status="blocker",
        pr_input=pr_input,
        ai_signal_summary=failure.message,
    )
    rendered_report = render_text_report(report)

    assert failure.reason == "missing_token"
    assert "GITHUB_TOKEN" in failure.message
    assert unrelated_token not in str(caught.value)
    assert unrelated_token not in repr(caught.value)
    assert unrelated_token not in failure.model_dump_json()
    assert unrelated_token not in rendered_report


def test_explicit_env_overrides_api_base_and_token_env_name() -> None:
    """Catches adapters that force one global enterprise token naming convention."""
    token = "line_enterprise_secret_value"

    plan = resolve_github_api_plan(
        _self_hosted_pr_input("git.linecorp.com"),
        env={
            "PR_RADAR_GITHUB_API_BASE_URL": "https://ghe-proxy.internal/api/v3",
            "PR_RADAR_GITHUB_TOKEN_ENV": "LINE_GHE_TOKEN",
            "LINE_GHE_TOKEN": token,
            "GHE_TOKEN": "wrong-default-token",
        },
    )

    assert plan.api_base_url == "https://ghe-proxy.internal/api/v3"
    assert plan.auth_env_var == "LINE_GHE_TOKEN"
    assert plan.token == token


def test_custom_token_env_name_does_not_fallback_to_default_token() -> None:
    """Catches accidental auth against the wrong deployment when override is set."""
    default_token = "default_ghe_secret_value"

    with pytest.raises(GitHubAuthResolutionError) as caught:
        resolve_github_api_plan(
            _self_hosted_pr_input("git.linecorp.com"),
            env={
                "PR_RADAR_GITHUB_TOKEN_ENV": "LINE_GHE_TOKEN",
                "GHE_TOKEN": default_token,
            },
        )

    failure = caught.value.failure
    serialized_failure = failure.model_dump_json()
    assert failure.reason == "missing_token"
    assert "LINE_GHE_TOKEN" in failure.message
    assert "Missing GHE_TOKEN" not in failure.message
    assert default_token not in str(caught.value)
    assert default_token not in repr(caught.value)
    assert default_token not in serialized_failure


@pytest.mark.parametrize(
    "api_base_url",
    [
        "not a url",
        "ftp://ghe.internal/api/v3",
        "https://user:pass@ghe.internal/api/v3",
    ],
)
def test_explicit_api_base_url_must_be_report_safe_http_url(
    api_base_url: str,
) -> None:
    """Catches unsafe API base overrides that could leak credentials or misroute."""
    token = "line_enterprise_secret_value"

    with pytest.raises(GitHubAuthResolutionError) as caught:
        resolve_github_api_plan(
            _self_hosted_pr_input("git.linecorp.com"),
            env={
                "PR_RADAR_GITHUB_API_BASE_URL": api_base_url,
                "PR_RADAR_GITHUB_TOKEN_ENV": "LINE_GHE_TOKEN",
                "LINE_GHE_TOKEN": token,
            },
        )

    failure = caught.value.failure
    serialized_failure = failure.model_dump_json()
    assert failure.reason == "unsupported_deployment"
    assert token not in str(caught.value)
    assert token not in repr(caught.value)
    assert token not in serialized_failure
