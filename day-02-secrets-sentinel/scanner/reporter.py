"""
reporter.py — Multi-format report generation.

Supported output formats:
  • terminal  — colourised console table (default)
  • json      — machine-readable JSON
  • sarif     — SARIF v2.1.0 (GitHub Advanced Security / VS Code)
  • html      — self-contained HTML dashboard
  • csv       — flat CSV for BI / Data Analyst workflows
"""

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import List

from .detector import Finding, ScanStats

SEVERITY_COLORS = {
    "CRITICAL": "\033[91m",   # bright red
    "HIGH":     "\033[93m",   # yellow
    "MEDIUM":   "\033[94m",   # blue
    "LOW":      "\033[96m",   # cyan
}
RESET = "\033[0m"
BOLD  = "\033[1m"


# ──────────────────────────────────────────────────────────────────────────────
# Terminal reporter
# ──────────────────────────────────────────────────────────────────────────────

def report_terminal(findings: List[Finding], stats: ScanStats, no_color: bool = False) -> str:
    lines = []

    def c(color: str, text: str) -> str:
        return text if no_color else f"{color}{text}{RESET}"

    lines.append("")
    lines.append(c(BOLD, "╔══════════════════════════════════════════════════════╗"))
    lines.append(c(BOLD, "║         SecretSentinel — Scan Report                 ║"))
    lines.append(c(BOLD, "╚══════════════════════════════════════════════════════╝"))
    lines.append(f"  Scanned   : {stats.files_scanned} files  |  {stats.lines_scanned:,} lines")
    lines.append(f"  Elapsed   : {stats.elapsed_seconds}s")
    lines.append(f"  Findings  : {stats.findings_total} total  "
                 f"[{c(SEVERITY_COLORS['CRITICAL'], str(stats.findings_critical) + ' CRITICAL')}  "
                 f"{c(SEVERITY_COLORS['HIGH'], str(stats.findings_high) + ' HIGH')}  "
                 f"{c(SEVERITY_COLORS['MEDIUM'], str(stats.findings_medium) + ' MEDIUM')}  "
                 f"{c(SEVERITY_COLORS['LOW'], str(stats.findings_low) + ' LOW')}]")
    lines.append("")

    if not findings:
        lines.append(c("\033[92m", "  ✓ No secrets detected."))
        return "\n".join(lines)

    for f in findings:
        sev_col = SEVERITY_COLORS.get(f.severity, "")
        lines.append(c(sev_col, f"  [{f.severity}]") + f"  {f.pattern_name}")
        lines.append(f"    File     : {f.file}:{f.line_no}")
        lines.append(f"    Value    : {f.matched_value}")
        if f.entropy:
            lines.append(f"    Entropy  : {f.entropy} bits/char")
        if f.hint:
            lines.append(f"    Hint     : {f.hint}")
        if f.roles:
            lines.append(f"    Roles    : {', '.join(f.roles)}")
        lines.append(f"    Line     : {f.line.strip()[:120]}")
        lines.append(f"    ID       : {f.fingerprint}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# JSON reporter
# ──────────────────────────────────────────────────────────────────────────────

def report_json(findings: List[Finding], stats: ScanStats, scan_root: str = ".") -> str:
    return json.dumps({
        "tool": "SecretSentinel",
        "version": "1.0.0",
        "scan_root": os.path.abspath(scan_root),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "files_scanned":    stats.files_scanned,
            "lines_scanned":    stats.lines_scanned,
            "elapsed_seconds":  stats.elapsed_seconds,
            "findings_total":   stats.findings_total,
            "by_severity": {
                "CRITICAL": stats.findings_critical,
                "HIGH":     stats.findings_high,
                "MEDIUM":   stats.findings_medium,
                "LOW":      stats.findings_low,
            },
        },
        "findings": [
            {
                "fingerprint":    f.fingerprint,
                "severity":       f.severity,
                "pattern_id":     f.pattern_id,
                "pattern_name":   f.pattern_name,
                "file":           f.file,
                "line":           f.line_no,
                "matched_value":  f.matched_value,
                "entropy":        f.entropy,
                "hint":           f.hint,
                "roles":          f.roles,
                "line_content":   f.line.strip()[:200],
            }
            for f in findings
        ],
    }, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# SARIF v2.1.0 reporter (GitHub Advanced Security compatible)
# ──────────────────────────────────────────────────────────────────────────────

_SARIF_SEVERITY = {
    "CRITICAL": "error",
    "HIGH":     "error",
    "MEDIUM":   "warning",
    "LOW":      "note",
}

def report_sarif(findings: List[Finding], stats: ScanStats, scan_root: str = ".") -> str:
    rules = {}
    for f in findings:
        if f.pattern_id not in rules:
            rules[f.pattern_id] = {
                "id": f.pattern_id,
                "name": f.pattern_name,
                "shortDescription": {"text": f.pattern_name},
                "fullDescription":  {"text": f.hint or f.pattern_name},
                "defaultConfiguration": {
                    "level": _SARIF_SEVERITY.get(f.severity, "warning")
                },
                "properties": {
                    "tags": f.roles,
                    "severity": f.severity,
                },
            }

    results = []
    for f in findings:
        results.append({
            "ruleId": f.pattern_id,
            "level": _SARIF_SEVERITY.get(f.severity, "warning"),
            "message": {
                "text": (
                    f"{f.pattern_name} detected. "
                    f"Matched value (redacted): {f.matched_value}. "
                    + (f"Entropy: {f.entropy} bits/char. " if f.entropy else "")
                    + (f"Hint: {f.hint}" if f.hint else "")
                )
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": f.file,
                        "uriBaseId": "%SRCROOT%",
                    },
                    "region": {
                        "startLine": f.line_no,
                        "snippet":   {"text": f.line.strip()[:200]},
                    },
                }
            }],
            "fingerprints": {"secretSentinel/v1": f.fingerprint},
            "properties":   {"severity": f.severity, "roles": f.roles},
        })

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name":            "SecretSentinel",
                    "version":         "1.0.0",
                    "informationUri":  "https://github.com/Sadhik2607/daily-builds",
                    "rules":           list(rules.values()),
                }
            },
            "results":   results,
            "invocations": [{
                "executionSuccessful": True,
                "toolExecutionNotifications": [],
            }],
        }],
    }
    return json.dumps(sarif, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# CSV reporter
# ──────────────────────────────────────────────────────────────────────────────

def report_csv(findings: List[Finding], stats: ScanStats) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "severity", "pattern_id", "pattern_name", "file", "line_no",
        "matched_value", "entropy", "roles", "hint", "fingerprint",
    ])
    writer.writeheader()
    for f in findings:
        writer.writerow({
            "severity":     f.severity,
            "pattern_id":   f.pattern_id,
            "pattern_name": f.pattern_name,
            "file":         f.file,
            "line_no":      f.line_no,
            "matched_value": f.matched_value,
            "entropy":      f.entropy or "",
            "roles":        "|".join(f.roles),
            "hint":         f.hint,
            "fingerprint":  f.fingerprint,
        })
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# HTML reporter
# ──────────────────────────────────────────────────────────────────────────────

def report_html(findings: List[Finding], stats: ScanStats, scan_root: str = ".") -> str:
    if not findings:
        no_findings_block = '<p class="no-findings">&#x2705; No secrets detected. Clean scan!</p>'
    else:
        no_findings_block = f"""<table>
  <thead>
    <tr>
      <th>Severity</th><th>Pattern</th><th>Location</th>
      <th>Value (redacted)</th><th>Entropy</th><th>Roles</th><th>Hint</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    sev_colors = {
        "CRITICAL": "#ef4444",
        "HIGH":     "#f97316",
        "MEDIUM":   "#eab308",
        "LOW":      "#3b82f6",
    }

    rows = ""
    for f in findings:
        color = sev_colors.get(f.severity, "#6b7280")
        entropy_td = f"{f.entropy:.3f}" if f.entropy else "—"
        roles_td = ", ".join(f.roles) if f.roles else "—"
        rows += f"""
        <tr>
          <td><span class="badge" style="background:{color}">{f.severity}</span></td>
          <td>{_esc(f.pattern_name)}</td>
          <td class="mono">{_esc(f.file)}:{f.line_no}</td>
          <td class="mono">{_esc(f.matched_value)}</td>
          <td>{entropy_td}</td>
          <td>{roles_td}</td>
          <td class="hint">{_esc(f.hint)}</td>
        </tr>"""

    scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SecretSentinel Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
  h1 {{ font-size: 1.8rem; color: #38bdf8; margin-bottom: .25rem; }}
  .subtitle {{ color: #64748b; font-size: .9rem; margin-bottom: 2rem; }}
  .stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1rem 1.5rem; min-width: 140px; }}
  .stat-num {{ font-size: 2rem; font-weight: 700; }}
  .stat-label {{ font-size: .8rem; color: #64748b; margin-top: .2rem; }}
  .critical {{ color: #ef4444; }} .high {{ color: #f97316; }}
  .medium {{ color: #eab308; }} .low {{ color: #3b82f6; }} .ok {{ color: #22c55e; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ background: #1e293b; padding: .8rem 1rem; text-align: left; font-size: .75rem;
        color: #64748b; text-transform: uppercase; letter-spacing: .05em; border-bottom: 1px solid #334155; }}
  td {{ padding: .75rem 1rem; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  tr:hover td {{ background: #1e293b55; }}
  .badge {{ display: inline-block; padding: .2rem .6rem; border-radius: 6px;
            font-size: .75rem; font-weight: 700; color: #fff; }}
  .mono {{ font-family: 'Fira Code', monospace; font-size: .8rem; word-break: break-all; }}
  .hint {{ color: #64748b; font-size: .78rem; }}
  .no-findings {{ text-align: center; padding: 3rem; color: #22c55e; font-size: 1.2rem; }}
</style>
</head>
<body>
<h1>🔐 SecretSentinel</h1>
<p class="subtitle">Scan of <code>{_esc(os.path.abspath(scan_root))}</code> — {scanned_at}</p>

<div class="stats">
  <div class="stat-card">
    <div class="stat-num">{stats.files_scanned}</div>
    <div class="stat-label">Files Scanned</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">{stats.lines_scanned:,}</div>
    <div class="stat-label">Lines Scanned</div>
  </div>
  <div class="stat-card">
    <div class="stat-num {'critical' if stats.findings_critical else 'ok'}">{stats.findings_critical}</div>
    <div class="stat-label">Critical</div>
  </div>
  <div class="stat-card">
    <div class="stat-num {'high' if stats.findings_high else 'ok'}">{stats.findings_high}</div>
    <div class="stat-label">High</div>
  </div>
  <div class="stat-card">
    <div class="stat-num {'medium' if stats.findings_medium else 'ok'}">{stats.findings_medium}</div>
    <div class="stat-label">Medium</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">{stats.elapsed_seconds}s</div>
    <div class="stat-label">Elapsed</div>
  </div>
</div>

{no_findings_block}
</body>
</html>"""


def _esc(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
