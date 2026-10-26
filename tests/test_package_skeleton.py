from importlib import import_module
from importlib.metadata import entry_points

import pytest
from typer.testing import CliRunner


def test_cli_help_exposes_scan_command() -> None:
    """Catches a missing Typer app or missing local scan command registration."""
    try:
        app = import_module("pr_radar.cli").app
    except ModuleNotFoundError as error:
        pytest.fail(f"expected importable pr_radar.cli module: {error}")

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "scan" in result.output


def test_project_exposes_pr_radar_console_script() -> None:
    """Catches a missing installable console script for the local CLI entry path."""
    scripts = entry_points(group="console_scripts")
    matching_scripts = [
        script for script in scripts if script.name == "pr-radar"
    ]

    assert matching_scripts
    assert matching_scripts[0].value == "pr_radar.cli:app"


def test_scan_subcommand_renders_local_baseline_report() -> None:
    """Catches a scan command that does not wire parser to report rendering."""
    app = import_module("pr_radar.cli").app

    result = CliRunner().invoke(
        app,
        ["scan", "https://github.com/example/repo/pull/17/files?plain=1"],
    )

    assert result.exit_code == 0
    assert "PR Radar Local Report" in result.output
    assert "Overall Status: safe" in result.output
    assert "PR: example/repo#17" in result.output
    assert "URL: https://github.com/example/repo/pull/17" in result.output
    assert "AI Signal: No AI-generation evidence collected yet." in result.output
    assert "Security & Supply Chain: No findings yet." in result.output


def test_scan_subcommand_fails_closed_for_invalid_pr_url() -> None:
    """Catches scan commands that silently accept non-PR URLs."""
    app = import_module("pr_radar.cli").app

    result = CliRunner().invoke(
        app,
        ["scan", "https://github.com/example/repo/issues/17"],
    )

    assert result.exit_code == 1
    assert "Invalid PR URL" in result.output
    assert "pull request path" in result.output


def test_scan_subcommand_hides_parser_tracebacks_for_malformed_ports() -> None:
    """Catches raw urllib parsing errors leaking into CLI output."""
    app = import_module("pr_radar.cli").app

    result = CliRunner().invoke(
        app,
        ["scan", "https://github.com:bad/example/repo/pull/17"],
    )

    assert result.exit_code == 1
    assert "Invalid PR URL" in result.output
    assert "port" in result.output
    assert "Traceback" not in result.output
    assert "ValueError" not in result.output


def test_scan_subcommand_renders_without_repository_fetch_access() -> None:
    """Catches scan commands that require network before baseline rendering."""
    app = import_module("pr_radar.cli").app

    result = CliRunner().invoke(
        app,
        ["scan", "https://git.example.internal/team/repo/pull/42"],
    )

    assert result.exit_code == 0
    assert "PR Radar Local Report" in result.output
    assert "PR: team/repo#42" in result.output
    assert "No AI-generation evidence collected yet." in result.output


def test_scan_subcommand_requires_pr_url_argument() -> None:
    """Catches scan commands that can run without the required PR URL."""
    app = import_module("pr_radar.cli").app

    result = CliRunner().invoke(app, ["scan"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output
