import typer

from pr_radar.application.scan import ScanError, scan_pr
from pr_radar.reporting.text import render_text_report

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """PR Radar local CLI."""


@app.command()
def scan(
    pr_url: str,
    fetch_evidence: bool = typer.Option(
        False,
        "--fetch-evidence",
        help="Fetch PR evidence locally before rendering the report.",
    ),
) -> None:
    """Render a baseline local PR radar report."""
    try:
        report = scan_pr(pr_url, fetch_evidence=fetch_evidence)
    except ScanError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1) from error

    typer.echo(render_text_report(report))
