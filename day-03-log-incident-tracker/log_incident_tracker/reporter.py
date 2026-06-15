"""
Multi-format report generator.

Outputs: terminal (colour via ANSI), JSON, CSV, and self-contained HTML.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .incident_tracker import Incident, MatchedEvent, SREMetrics
from .parser import LogEntry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_seconds(s: Optional[float]) -> str:
    if s is None:
        return "N/A"
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


_SEV_COLOUR = {
    "CRITICAL": "\033[91m",  # bright red
    "ERROR":    "\033[31m",  # red
    "WARNING":  "\033[33m",  # yellow
    "INFO":     "\033[36m",  # cyan
    "DEBUG":    "\033[37m",  # white
    "UNKNOWN":  "\033[90m",  # grey
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"

_SEV_ICON = {
    "CRITICAL": "🔴",
    "ERROR":    "🟠",
    "WARNING":  "🟡",
    "INFO":     "🔵",
}


# ── Terminal reporter ─────────────────────────────────────────────────────────

def report_terminal(
    incidents: List[Incident],
    metrics: SREMetrics,
    all_entries: List[LogEntry],
    matched_events: List[MatchedEvent],
    top_n: int = 10,
    use_colour: bool = True,
) -> str:
    lines: List[str] = []

    def c(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if use_colour else text

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(c("═" * 64, _BOLD))
    lines.append(c(f"  LogSentinel — Incident Report  [{now}]", _BOLD))
    lines.append(c("═" * 64, _BOLD))
    lines.append("")

    lines.append(c("📊 Summary", _BOLD))
    lines.append(f"  Total log lines      : {len(all_entries):>8,}")
    lines.append(f"  Matched events       : {len(matched_events):>8,}")
    lines.append(f"  Incidents detected   : {len(incidents):>8}")
    lines.append("")

    by_sev: dict[str, List[Incident]] = {}
    for inc in incidents:
        by_sev.setdefault(inc.severity, []).append(inc)

    for sev in ("CRITICAL", "ERROR", "WARNING", "INFO"):
        group = by_sev.get(sev, [])
        if not group:
            continue
        icon = _SEV_ICON.get(sev, "")
        colour = _SEV_COLOUR.get(sev, "")
        lines.append(c(f"{icon}  {sev}  — {len(group)} incident(s)", colour))
        for inc in group[:top_n]:
            ts = inc.first_seen.strftime("%Y-%m-%d %H:%M") if inc.first_seen else "unknown time"
            mttr_str = _fmt_seconds(inc.mttr_seconds or inc.duration_seconds)
            lines.append(f"  {inc.id}  [{ts}]  {inc.pattern.name}")
            lines.append(f"           events={inc.event_count}  duration={mttr_str}")
            lines.append(f"           ↳ {inc.sample_line[:100]}")
        lines.append("")

    lines.append(c("⚙️   SRE Metrics", _BOLD))
    lines.append(f"  MTTR  : {_fmt_seconds(metrics.mttr_seconds):<12} (Mean Time To Recovery)")
    lines.append(f"  MTTF  : {_fmt_seconds(metrics.mttf_seconds):<12} (Mean Time To Failure)")
    lines.append(f"  MTBF  : {_fmt_seconds(metrics.mtbf_seconds):<12} (Mean Time Between Failures)")
    lines.append(f"  Rate  : {metrics.incident_rate_per_hour:.2f} incidents/hour")
    lines.append(f"  Window: {_fmt_seconds(metrics.observation_window_seconds)}")
    lines.append("")

    return "\n".join(lines)


# ── JSON reporter ─────────────────────────────────────────────────────────────

def report_json(
    incidents: List[Incident],
    metrics: SREMetrics,
    all_entries: List[LogEntry],
    matched_events: List[MatchedEvent],
) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_lines":     len(all_entries),
            "matched_events":  len(matched_events),
            "incidents":       len(incidents),
        },
        "sre_metrics":  metrics.as_dict(),
        "incidents":    [i.as_dict() for i in incidents],
        "top_events":   [e.as_dict() for e in matched_events[:50]],
    }
    return json.dumps(payload, indent=2, default=str)


# ── CSV reporter ──────────────────────────────────────────────────────────────

def report_csv(
    incidents: List[Incident],
    output_path: Path,
) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "id", "severity", "pattern_id", "pattern_name", "category",
            "first_seen", "last_seen", "event_count", "duration_seconds",
            "mttr_seconds", "sample_line",
        ])
        writer.writeheader()
        for inc in incidents:
            writer.writerow({
                "id":               inc.id,
                "severity":         inc.severity,
                "pattern_id":       inc.pattern.id,
                "pattern_name":     inc.pattern.name,
                "category":         inc.pattern.category,
                "first_seen":       inc.first_seen.isoformat() if inc.first_seen else "",
                "last_seen":        inc.last_seen.isoformat() if inc.last_seen else "",
                "event_count":      inc.event_count,
                "duration_seconds": round(inc.duration_seconds or 0, 1),
                "mttr_seconds":     round(inc.mttr_seconds or 0, 1),
                "sample_line":      inc.sample_line[:200],
            })


# ── HTML reporter ─────────────────────────────────────────────────────────────

_SEV_CSS = {
    "CRITICAL": "#dc2626",
    "ERROR":    "#ea580c",
    "WARNING":  "#d97706",
    "INFO":     "#2563eb",
}

def report_html(
    incidents: List[Incident],
    metrics: SREMetrics,
    all_entries: List[LogEntry],
    matched_events: List[MatchedEvent],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def sev_badge(sev: str) -> str:
        colour = _SEV_CSS.get(sev, "#6b7280")
        return f'<span style="background:{colour};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold">{sev}</span>'

    incident_rows = ""
    for inc in incidents:
        ts = inc.first_seen.strftime("%Y-%m-%d %H:%M UTC") if inc.first_seen else "—"
        dur = _fmt_seconds(inc.duration_seconds)
        mttr = _fmt_seconds(inc.mttr_seconds)
        incident_rows += f"""
        <tr>
          <td>{inc.id}</td>
          <td>{sev_badge(inc.severity)}</td>
          <td>{inc.pattern.name}</td>
          <td>{ts}</td>
          <td>{inc.event_count:,}</td>
          <td>{dur}</td>
          <td><code style="font-size:11px">{inc.sample_line[:120].replace('<','&lt;')}</code></td>
        </tr>"""

    top_events_rows = ""
    for ev in matched_events[:30]:
        ts = ev.entry.timestamp.strftime("%H:%M:%S") if ev.entry.timestamp else "—"
        colour = _SEV_CSS.get(ev.pattern.severity, "#6b7280")
        top_events_rows += f"""
        <tr>
          <td style="color:{colour};font-weight:bold">{ev.pattern.severity}</td>
          <td>{ts}</td>
          <td>{ev.pattern.name}</td>
          <td><code style="font-size:11px">{ev.entry.raw_line[:120].replace('<','&lt;')}</code></td>
        </tr>"""

    def _metric(label: str, value: str, desc: str) -> str:
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:20px;text-align:center">
          <div style="font-size:28px;font-weight:bold;color:#f8fafc">{value}</div>
          <div style="font-size:14px;color:#94a3b8;margin-top:4px">{label}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">{desc}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LogSentinel — Incident Report</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
           background:#0f172a;color:#e2e8f0;margin:0;padding:24px }}
    h1   {{ color:#f8fafc;margin-bottom:4px }}
    h2   {{ color:#94a3b8;font-size:14px;font-weight:normal;margin-bottom:32px }}
    h3   {{ color:#cbd5e1;margin:32px 0 12px }}
    table {{ width:100%;border-collapse:collapse;margin-top:8px }}
    th,td {{ padding:10px 12px;text-align:left;border-bottom:1px solid #1e293b;font-size:13px }}
    th   {{ background:#1e293b;color:#94a3b8;font-weight:600 }}
    tr:hover td {{ background:#1e293b33 }}
    .grid {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:32px }}
    a    {{ color:#60a5fa }}
  </style>
</head>
<body>
  <h1>🔍 LogSentinel — Incident Report</h1>
  <h2>Generated: {now} · {len(incidents)} incidents detected · {len(all_entries):,} log lines processed</h2>

  <h3>SRE Metrics</h3>
  <div class="grid">
    {_metric("MTTR", _fmt_seconds(metrics.mttr_seconds), "Mean Time To Recovery")}
    {_metric("MTTF", _fmt_seconds(metrics.mttf_seconds), "Mean Time To Failure")}
    {_metric("MTBF", _fmt_seconds(metrics.mtbf_seconds), "Mean Time Between Failures")}
    {_metric("Rate", f"{metrics.incident_rate_per_hour:.2f}/hr", "Incidents per hour")}
    {_metric("CRITICAL", str(metrics.critical_count), "Critical incidents")}
    {_metric("ERROR", str(metrics.error_count), "Error incidents")}
  </div>

  <h3>Incidents ({len(incidents)})</h3>
  <table>
    <thead>
      <tr><th>ID</th><th>Severity</th><th>Pattern</th><th>First Seen</th>
          <th>Events</th><th>Duration</th><th>Sample</th></tr>
    </thead>
    <tbody>{incident_rows}</tbody>
  </table>

  <h3>Top Matched Events (first 30)</h3>
  <table>
    <thead>
      <tr><th>Severity</th><th>Time</th><th>Pattern</th><th>Log Line</th></tr>
    </thead>
    <tbody>{top_events_rows}</tbody>
  </table>

  <p style="color:#475569;font-size:12px;margin-top:48px">
    LogSentinel · Day 03 Daily Build ·
    <a href="https://github.com/Sadhik2607/daily-builds/tree/main/day-03-log-incident-tracker">GitHub</a>
  </p>
</body>
</html>"""


# ── Dispatcher ────────────────────────────────────────────────────────────────

def write_reports(
    incidents:      List[Incident],
    metrics:        SREMetrics,
    all_entries:    List[LogEntry],
    matched_events: List[MatchedEvent],
    formats:        List[str],       # ["terminal","json","html","csv","all"]
    output_dir:     Path,
    top_n:          int = 10,
) -> dict[str, Optional[Path]]:
    """Write requested formats; return dict of format → output path (None = stdout)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Optional[Path]] = {}

    want = set(formats)
    if "all" in want:
        want = {"terminal", "json", "html", "csv"}

    if "terminal" in want:
        print(report_terminal(incidents, metrics, all_entries, matched_events, top_n=top_n))
        results["terminal"] = None

    if "json" in want:
        p = output_dir / "incidents.json"
        p.write_text(report_json(incidents, metrics, all_entries, matched_events), encoding="utf-8")
        results["json"] = p

    if "html" in want:
        p = output_dir / "incidents.html"
        p.write_text(report_html(incidents, metrics, all_entries, matched_events), encoding="utf-8")
        results["html"] = p

    if "csv" in want:
        p = output_dir / "incidents.csv"
        report_csv(incidents, p)
        results["csv"] = p

    return results
