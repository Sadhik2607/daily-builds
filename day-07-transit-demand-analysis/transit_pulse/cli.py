"""TransitPulse CLI."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from transit_pulse import db, forecasting, metrics, reporters

console = Console()


@click.group()
def cli():
    """TransitPulse — Transit Demand & Performance Analyzer."""


@cli.command()
@click.argument("dsn")
@click.option("--format", "fmt", type=click.Choice(["terminal", "json", "html", "csv", "all"]), default="terminal")
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("./reports"))
@click.option("--forecast-days", type=int, default=14, help="Days ahead to project ridership.")
@click.option("--fail-under", type=float, default=None, help="Exit 1 if system on-time %% falls below this threshold.")
def analyze(dsn: str, fmt: str, output_dir: Path, forecast_days: int, fail_under: float | None):
    """Analyze ridership and service performance from DSN (sqlite path or any SQLAlchemy URL)."""
    engine = db.get_engine(dsn)
    missing = db.validate_schema(engine)
    if missing:
        console.print(f"[bold red]Missing required tables:[/bold red] {missing}")
        sys.exit(2)

    tables = db.load_tables(engine)
    routes, ridership, perf = tables["routes"], tables["ridership_daily"], tables["service_performance"]

    daily_total = ridership.copy()
    daily_total["date"] = __import__("pandas").to_datetime(daily_total["date"])
    daily_series = daily_total.groupby("date")["boardings"].sum()

    results = {
        "demand": metrics.demand_patterns(ridership),
        "seasonal": metrics.seasonal_trends(ridership),
        "utilization": metrics.utilization(ridership, routes),
        "performance": metrics.performance_indicators(perf),
        "forecast": forecasting.forecast_series(daily_series, horizon_days=forecast_days),
    }
    scorecard = metrics.route_scorecard(ridership, routes, perf)

    output_dir.mkdir(parents=True, exist_ok=True)

    if fmt in ("terminal", "all"):
        reporters.render_terminal(results, scorecard)
    if fmt in ("json", "all"):
        p = reporters.to_json(results, scorecard, output_dir)
        console.print(f"[green]JSON report:[/green] {p}")
    if fmt in ("csv", "all"):
        p = reporters.to_csv(scorecard, output_dir)
        console.print(f"[green]CSV report:[/green] {p}")
    if fmt in ("html", "all"):
        p = reporters.to_html(results, scorecard, output_dir)
        console.print(f"[green]HTML report:[/green] {p}")

    if fail_under is not None and results["performance"]["overall_on_time_pct"] < fail_under:
        console.print(
            f"[bold red]FAIL:[/bold red] system on-time {results['performance']['overall_on_time_pct']}% "
            f"< threshold {fail_under}%"
        )
        sys.exit(1)


@cli.command()
@click.argument("dsn")
def routes(dsn: str):
    """List routes and their basic stats."""
    engine = db.get_engine(dsn)
    tables = db.load_tables(engine)
    console.print(tables["routes"].to_string(index=False))


def main():
    cli()


if __name__ == "__main__":
    main()
