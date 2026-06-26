"""Terminal, JSON, CSV, and HTML reporters for a list of DatasetReport."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .monitor import DatasetReport

_STATUS_COLOR = {"CRITICAL": "#e5484d", "WARNING": "#f5a623", "OK": "#2eb872"}


def to_terminal(reports: list[DatasetReport], elapsed_s: float) -> str:
    lines = [
        f"PBI-Pulse — scanned {len({r.workspace for r in reports})} workspaces, "
        f"{len(reports)} datasets in {elapsed_s:.1f}s",
        "-" * 62,
    ]
    issue_count = 0
    for r in sorted(reports, key=lambda r: r.health_score):
        tag = f"[{r.status}]".ljust(11)
        lines.append(f"{tag}{r.workspace} / {r.dataset}   score={r.health_score}")
        for issue in r.issues:
            issue_count += 1
            lines.append(f"   - {issue.detail}")
    lines.append("-" * 62)
    lines.append(f"{issue_count} issues found across {len(reports)} datasets.")
    return "\n".join(lines)


def to_json(reports: list[DatasetReport]) -> dict:
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "datasets": [
            {
                "workspace": r.workspace,
                "dataset": r.dataset,
                "dataset_id": r.dataset_id,
                "health_score": r.health_score,
                "status": r.status,
                "last_refresh_end": r.last_refresh_end,
                "issues": [
                    {"rule": i.rule, "severity": i.severity, "detail": i.detail}
                    for i in r.issues
                ],
            }
            for r in reports
        ],
    }


def write_json(reports: list[DatasetReport], out_dir: Path) -> Path:
    path = out_dir / "report.json"
    path.write_text(json.dumps(to_json(reports), indent=2))
    return path


def write_csv(reports: list[DatasetReport], out_dir: Path) -> Path:
    path = out_dir / "report.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["workspace", "dataset", "health_score", "severity", "rule", "detail", "last_refresh_end"])
        for r in reports:
            if not r.issues:
                writer.writerow([r.workspace, r.dataset, r.health_score, "OK", "", "", r.last_refresh_end])
            for issue in r.issues:
                writer.writerow([r.workspace, r.dataset, r.health_score, issue.severity, issue.rule, issue.detail, r.last_refresh_end])
    return path


_HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>PBI-Pulse Report</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0c0c0f;color:#e7e7ea;margin:0;padding:32px;}}
h1{{font-size:20px;margin-bottom:4px;}}
.meta{{color:#9a9aa2;font-size:13px;margin-bottom:24px;}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
th{{text-align:left;color:#9a9aa2;font-weight:500;padding:10px 12px;border-bottom:1px solid #2a2a30;}}
td{{padding:10px 12px;border-bottom:1px solid #1c1c20;vertical-align:top;}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;color:#0c0c0f;}}
.score{{font-weight:600;}}
.issues{{color:#c7c7cc;font-size:13px;}}
</style></head>
<body>
<h1>PBI-Pulse Health Report</h1>
<div class="meta">Generated {scanned_at} &middot; {dataset_count} datasets &middot; {issue_count} issues</div>
<table>
<tr><th>Status</th><th>Workspace</th><th>Dataset</th><th>Score</th><th>Last refresh</th><th>Issues</th></tr>
{rows}
</table>
</body></html>
"""

_ROW_TEMPLATE = """<tr>
<td><span class="badge" style="background:{color}">{status}</span></td>
<td>{workspace}</td><td>{dataset}</td>
<td class="score">{score}</td>
<td>{last_refresh}</td>
<td class="issues">{issues}</td>
</tr>"""


def write_html(reports: list[DatasetReport], out_dir: Path) -> Path:
    rows = []
    issue_count = 0
    for r in sorted(reports, key=lambda r: r.health_score):
        issue_count += len(r.issues)
        issues_html = "<br>".join(i.detail for i in r.issues) or "&mdash;"
        rows.append(
            _ROW_TEMPLATE.format(
                color=_STATUS_COLOR[r.status],
                status=r.status,
                workspace=r.workspace,
                dataset=r.dataset,
                score=r.health_score,
                last_refresh=r.last_refresh_end or "never",
                issues=issues_html,
            )
        )
    html = _HTML_TEMPLATE.format(
        scanned_at=datetime.now(timezone.utc).isoformat(),
        dataset_count=len(reports),
        issue_count=issue_count,
        rows="\n".join(rows),
    )
    path = out_dir / "report.html"
    path.write_text(html)
    return path


def write_all(reports: list[DatasetReport], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "json": write_json(reports, out_dir),
        "csv": write_csv(reports, out_dir),
        "html": write_html(reports, out_dir),
    }
