"""Click CLI entrypoint: `python -m pbi_pulse.cli scan [options]`."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import click
import requests

from .auth import PowerBICredentials, TokenProvider
from .client import DemoPowerBIClient, PowerBIClient
from .monitor import scan as run_scan
from .reporters import to_terminal, write_all

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


@click.group()
def cli():
    """PBI-Pulse — Power BI workspace & dataset health monitor."""


@cli.command()
@click.option("--demo", is_flag=True, help="Use bundled sample data instead of live API calls")
@click.option("--workspace", multiple=True, help="Filter to one workspace name (repeatable)")
@click.option("--max-age-hours", default=26, show_default=True, type=int)
@click.option("--max-duration-min", default=60, show_default=True, type=int)
@click.option("--out", default="./reports", type=click.Path(), help="Output directory")
@click.option("--fail-under", default=None, type=int, help="Exit 1 if any dataset score is below this")
@click.option("--webhook", default=None, help="POST a summary to this Teams/Slack incoming webhook URL")
def scan(demo, workspace, max_age_hours, max_duration_min, out, fail_under, webhook):
    """Run a health scan and write terminal/json/csv/html reports."""
    started = time.monotonic()

    if demo:
        client = DemoPowerBIClient(SAMPLE_DIR)
    else:
        creds = PowerBICredentials.from_env()
        client = PowerBIClient(TokenProvider(creds))

    reports = run_scan(
        client,
        workspace_filter=list(workspace) or None,
        max_age_hours=max_age_hours,
        max_duration_min=max_duration_min,
    )

    elapsed = time.monotonic() - started
    click.echo(to_terminal(reports, elapsed))

    out_dir = Path(out)
    paths = write_all(reports, out_dir)
    click.echo(f"\nReports written to {out_dir}/ ({', '.join(p.name for p in paths.values())})")

    if webhook:
        _post_webhook(webhook, reports)

    worst = min((r.health_score for r in reports), default=100)
    if fail_under is not None and worst < fail_under:
        click.echo(f"\nFAIL: worst dataset score {worst} < --fail-under {fail_under}", err=True)
        sys.exit(1)


def _post_webhook(url: str, reports) -> None:
    critical = [r for r in reports if r.status == "CRITICAL"]
    warning = [r for r in reports if r.status == "WARNING"]
    text = (
        f"PBI-Pulse: {len(critical)} critical, {len(warning)} warning dataset(s) "
        f"out of {len(reports)} scanned."
    )
    try:
        requests.post(url, json={"text": text}, timeout=10)
    except requests.RequestException as exc:  # pragma: no cover - network
        click.echo(f"Webhook post failed: {exc}", err=True)


if __name__ == "__main__":
    cli()
