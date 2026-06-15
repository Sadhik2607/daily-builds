"""
LogSentinel CLI entry point.

Usage:
  python -m log_incident_tracker.cli scan LOGFILE [OPTIONS]
  python -m log_incident_tracker.cli metrics LOGFILE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .incident_tracker import cluster_incidents, compute_sre_metrics, match_events
from .notifier import notify
from .parser import LogType, parse_file
from .reporter import _fmt_seconds, write_reports


def _build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="log-sentinel",
        description="LogSentinel — Multi-format log parser and incident tracker",
    )
    sub = root.add_subparsers(dest="command")

    # ── scan ──────────────────────────────────────────────────────────────────
    scan = sub.add_parser("scan", help="Parse a log file and produce an incident report")
    scan.add_argument("file", metavar="FILE", help="Log file path (use - for stdin)")
    scan.add_argument(
        "--format", dest="formats", default=["terminal"], nargs="+",
        choices=["terminal", "json", "html", "csv", "all"],
        help="Output format(s) (default: terminal)",
    )
    scan.add_argument("--output-dir", default="./output", help="Directory for file outputs")
    scan.add_argument(
        "--log-type", default="auto",
        choices=[t.value for t in LogType],
        help="Force log format (default: auto-detect)",
    )
    scan.add_argument(
        "--window", type=int, default=300,
        help="Incident clustering window in seconds (default: 300)",
    )
    scan.add_argument(
        "--threshold", type=int, default=1,
        help="Minimum events to declare an incident (default: 1)",
    )
    scan.add_argument(
        "--severity", default="WARNING",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        help="Minimum severity to include (default: WARNING)",
    )
    scan.add_argument("--slack-webhook", default=None, help="Slack incoming webhook URL")
    scan.add_argument("--webhook", default=None, help="Generic webhook URL")
    scan.add_argument("--top", type=int, default=10, help="Top N patterns in terminal output")

    # ── metrics ───────────────────────────────────────────────────────────────
    metrics = sub.add_parser("metrics", help="Print SRE metrics for a log file")
    metrics.add_argument("file", metavar="FILE")
    metrics.add_argument("--log-type", default="auto", choices=[t.value for t in LogType])
    metrics.add_argument("--window", type=int, default=300)

    # ── formats ───────────────────────────────────────────────────────────────
    sub.add_parser("formats", help="List supported log formats")

    return root


def _run_scan(args: argparse.Namespace) -> int:
    file_path = None if args.file == "-" else args.file
    log_type  = LogType(args.log_type)
    output_dir = Path(args.output_dir)

    print(f"[logsentinel] parsing {args.file} …", file=sys.stderr)
    entries = list(parse_file(file_path, log_type))
    print(f"[logsentinel] {len(entries):,} entries parsed", file=sys.stderr)

    events = match_events(entries)
    print(f"[logsentinel] {len(events):,} events matched", file=sys.stderr)

    incidents = cluster_incidents(events, window_seconds=args.window, min_events=args.threshold)
    metrics   = compute_sre_metrics(incidents, entries)

    _sev_order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    _threshold = _sev_order.get(args.severity, 2)
    visible_incidents = [i for i in incidents if _sev_order.get(i.severity, 99) <= _threshold]

    write_reports(
        incidents=visible_incidents,
        metrics=metrics,
        all_entries=entries,
        matched_events=events,
        formats=args.formats,
        output_dir=output_dir,
        top_n=args.top,
    )

    notify(
        incidents=visible_incidents,
        metrics=metrics,
        log_source=args.file,
        slack_webhook=args.slack_webhook,
        generic_webhook=args.webhook,
        min_severity=args.severity,
    )

    return 1 if any(i.severity == "CRITICAL" for i in incidents) else 0


def _run_metrics(args: argparse.Namespace) -> int:
    log_type = LogType(args.log_type)
    entries  = list(parse_file(args.file if args.file != "-" else None, log_type))
    events   = match_events(entries)
    incidents = cluster_incidents(events, window_seconds=args.window)
    m = compute_sre_metrics(incidents, entries)

    print(f"MTTR  : {_fmt_seconds(m.mttr_seconds)}")
    print(f"MTTF  : {_fmt_seconds(m.mttf_seconds)}")
    print(f"MTBF  : {_fmt_seconds(m.mtbf_seconds)}")
    print(f"Rate  : {m.incident_rate_per_hour:.3f} incidents/hour")
    print(f"Total : {m.total_incidents} incidents")
    return 0


def _run_formats() -> int:
    rows = [
        ("apache",  "Apache CLF",         '"GET /path HTTP/1.1" 200'),
        ("nginx",   "NGINX error log",     "2026/06/14 03:12:17 [error] 42#0:"),
        ("python",  "Python logging",      "2026-06-14 03:12:17,042 ERROR app:"),
        ("jsonl",   "JSON Lines",          '{"timestamp":"…","level":"ERROR","msg":"…"}'),
        ("syslog",  "RFC 3164 syslog",     "Jun 14 03:12:17 host proc[pid]:"),
        ("plain",   "Plain text fallback", "(anything else)"),
    ]
    print(f"{'Type':<10} {'Description':<25} {'Example prefix'}")
    print("-" * 70)
    for fmt, desc, ex in rows:
        print(f"{fmt:<10} {desc:<25} {ex}")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args   = parser.parse_args(argv)

    if args.command == "scan":
        return _run_scan(args)
    if args.command == "metrics":
        return _run_metrics(args)
    if args.command == "formats":
        return _run_formats()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
