"""Output reporters: terminal (rich), JSON, CSV, and a self-contained HTML
dashboard with inline SVG charts (no JS/CDN dependency — same "dependency-free,
emailable" pattern used by the other daily-builds reports).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table


def render_terminal(results: dict, scorecard: pd.DataFrame) -> None:
    console = Console()
    console.rule("[bold cyan]TransitPulse — Demand & Performance Report")

    d = results["demand"]
    console.print(f"[bold]Total boardings:[/bold] {d['total_boardings']:,}")
    console.print(f"[bold]Weekday/Weekend ridership ratio:[/bold] {d['weekday_vs_weekend_ratio']}")

    perf = results["performance"]
    console.print(
        f"[bold]System on-time performance:[/bold] {perf['overall_on_time_pct']}%   "
        f"[bold]Completion rate:[/bold] {perf['overall_completion_rate']}%   "
        f"[bold]Avg delay:[/bold] {perf['overall_avg_delay_minutes']} min"
    )

    util = results["utilization"]
    console.print(
        f"[bold]Avg load factor:[/bold] {util['overall_avg_load_factor']}   "
        f"(peak: {util['peak_avg_load_factor']}, off-peak: {util['offpeak_avg_load_factor']})"
    )

    fc = results["forecast"]
    trend_color = {"rising": "green", "declining": "red", "flat": "yellow"}.get(fc["trend"], "white")
    console.print(
        f"[bold]14-day ridership trend:[/bold] [{trend_color}]{fc['trend'].upper()}[/{trend_color}] "
        f"({fc['slope_pct_of_avg_per_day']}%/day off a {fc['current_avg_daily_boardings']:,.0f}/day baseline)"
    )

    cols = ["route_id", "total_boardings", "load_factor", "on_time_pct", "completion_rate", "avg_delay_minutes", "score"]
    table = Table(title="Route Scorecard (ranked)")
    for col in cols:
        table.add_column(col)
    for _, row in scorecard.iterrows():
        table.add_row(*[str(row[c]) for c in cols])
    console.print(table)

    if util["overcrowded_routes"]:
        console.print(f"[bold red]Overcrowded routes (load factor > 0.9):[/bold red] {list(util['overcrowded_routes'].keys())}")
    if util["underused_routes"]:
        console.print(f"[bold yellow]Underused routes (load factor < 0.25):[/bold yellow] {list(util['underused_routes'].keys())}")


def to_json(results: dict, scorecard: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "report.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **results,
        "route_scorecard": scorecard.to_dict(orient="records"),
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def to_csv(scorecard: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "route_scorecard.csv"
    scorecard.to_csv(path, index=False)
    return path


def _svg_bar_chart(data: dict, width=640, height=220, color="#3b82f6") -> str:
    if not data:
        return "<p>No data</p>"
    items = list(data.items())
    max_v = max(v for _, v in items) or 1
    bar_w = width / max(len(items), 1)
    bars = []
    for i, (label, value) in enumerate(items):
        h = (value / max_v) * (height - 40)
        x = i * bar_w + 4
        y = height - 30 - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 8:.1f}" height="{h:.1f}" fill="{color}" rx="3"/>'
            f'<text x="{x + (bar_w - 8) / 2:.1f}" y="{height - 12}" font-size="10" text-anchor="middle" fill="#555">{label}</text>'
            f'<text x="{x + (bar_w - 8) / 2:.1f}" y="{y - 4:.1f}" font-size="10" text-anchor="middle" fill="#222">{int(value):,}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">{"".join(bars)}</svg>'


def _svg_line_chart(series: dict, forecast: dict, width=720, height=240) -> str:
    if not series:
        return "<p>No data</p>"
    hist_vals = list(series.values())
    fc_vals = list(forecast.values())
    all_vals = hist_vals + fc_vals
    max_v, min_v = max(all_vals), min(all_vals)
    span = (max_v - min_v) or 1
    total_n = len(hist_vals) + len(fc_vals)
    step = width / max(total_n - 1, 1)

    def pt(i, v):
        x = i * step
        y = height - 30 - ((v - min_v) / span) * (height - 50)
        return x, y

    hist_pts = [pt(i, v) for i, v in enumerate(hist_vals)]
    fc_pts = [pt(i + len(hist_vals) - 1, v) for i, v in enumerate([hist_vals[-1]] + fc_vals)]

    hist_path = " ".join(f"{x:.1f},{y:.1f}" for x, y in hist_pts)
    fc_path = " ".join(f"{x:.1f},{y:.1f}" for x, y in fc_pts)

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">'
        f'<polyline points="{hist_path}" fill="none" stroke="#2563eb" stroke-width="2"/>'
        f'<polyline points="{fc_path}" fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="5,4"/>'
        f'<text x="4" y="14" font-size="11" fill="#2563eb">— actual (7d rolling avg)</text>'
        f'<text x="180" y="14" font-size="11" fill="#f97316">- - forecast</text>'
        f"</svg>"
    )


def to_html(results: dict, scorecard: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "report.html"
    d, util, perf, fc = results["demand"], results["utilization"], results["performance"], results["forecast"]

    rows = "".join(
        f"<tr><td>{r.route_id}</td><td>{r.total_boardings:,}</td><td>{r.load_factor}</td>"
        f"<td>{r.on_time_pct}%</td><td>{r.completion_rate}%</td><td>{r.avg_delay_minutes} min</td>"
        f"<td><b>{r.score}</b></td></tr>"
        for r in scorecard.itertuples()
    )

    rolling = results["seasonal"]["rolling_7d_avg_series"]
    last_30 = dict(list(rolling.items())[-30:])

    trend_badge = {"rising": "#16a34a", "declining": "#dc2626", "flat": "#ca8a04"}.get(fc["trend"], "#555")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>TransitPulse Report</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f7f9;color:#1a1a1a;margin:0;padding:32px;}}
.container{{max-width:1000px;margin:0 auto;}}
h1{{font-size:22px;margin-bottom:4px;}} .sub{{color:#666;margin-bottom:24px;}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;}}
.card{{background:white;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08);}}
.card .label{{font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.05em;}}
.card .value{{font-size:24px;font-weight:700;margin-top:4px;}}
.panel{{background:white;border-radius:10px;padding:20px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.08);}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #eee;}}
th{{color:#888;font-weight:600;text-transform:uppercase;font-size:11px;}}
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;color:white;font-size:12px;font-weight:600;}}
</style></head><body><div class="container">
<h1>TransitPulse — Demand &amp; Performance Report</h1>
<p class="sub">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="cards">
  <div class="card"><div class="label">Total Boardings</div><div class="value">{d['total_boardings']:,}</div></div>
  <div class="card"><div class="label">On-Time Performance</div><div class="value">{perf['overall_on_time_pct']}%</div></div>
  <div class="card"><div class="label">Avg Load Factor</div><div class="value">{util['overall_avg_load_factor']}</div></div>
  <div class="card"><div class="label">14d Trend</div><div class="value"><span class="badge" style="background:{trend_badge}">{fc['trend'].upper()}</span></div></div>
</div>

<div class="panel"><h3>Ridership by Route</h3>{_svg_bar_chart(d['by_route'])}</div>
<div class="panel"><h3>30-Day Rolling Average + 14-Day Forecast</h3>{_svg_line_chart(last_30, fc['forecast'])}</div>

<div class="panel">
<h3>Route Scorecard</h3>
<table><thead><tr><th>Route</th><th>Boardings</th><th>Load Factor</th><th>On-Time %</th><th>Completion %</th><th>Avg Delay</th><th>Score</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>

</div></body></html>"""
    path.write_text(html)
    return path
