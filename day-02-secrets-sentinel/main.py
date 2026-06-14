#!/usr/bin/env python3
"""
SecretSentinel — Enterprise Secrets Scanner
===========================================
CLI entry point. Wraps the detector + reporter pipeline with a full
argparse interface, exit-code conventions, and baseline support.

Usage:
    python main.py [TARGET] [OPTIONS]

Exit codes:
    0 — No findings
    1 — Findings below or at threshold severity
    2 — CRITICAL findings detected
    3 — Scan error
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running as `python main.py` from project root
sys.path.insert(0, str(Path(__file__).parent))

from scanner.detector import SecretDetector
from scanner.reporter import (
    report_terminal,
    report_json,
    report_sarif,
    report_html,
    report_csv,
)

BANNER = r"""
  ____                    _   ____            _   _            _
 / ___|  ___  ___ _ __ __|_| / ___|  ___ _ __| |_(_)_ __   ___| |
 \___ \ / _ \/ __| '__/ _ \ | |  _ / _ \ '__| __| | '_ \ / _ \ |
  ___) |  __/ (__| | |  __/ | |_| |  __/ |  | |_| | | | |  __/ |
 |____/ \___|\___|_|  \___|  \____|\___|_|   \__|_|_| |_|\___|_|

  Enterprise Secrets Scanner v1.0.0
  github.com/Sadhik2607/daily-builds/day-02-secrets-sentinel
"""


def parse_args():
    parser = argparse.ArgumentParser(
        prog="secretsentinel",
        description="Scan codebases for leaked secrets, tokens, and credentials.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py .                              # scan current directory
  python main.py ./src --severity HIGH          # only HIGH+ findings
  python main.py . --format sarif -o results.sarif   # SARIF for GitHub
  python main.py . --format html  -o report.html     # HTML dashboard
  python main.py . --no-entropy                # skip entropy analysis
  python main.py . --baseline baseline.json    # suppress known findings
  python main.py . --fail-on CRITICAL          # exit 2 on any CRITICAL
        """,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Directory or file to scan (default: current directory)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["terminal", "json", "sarif", "html", "csv"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--severity", "-s",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=None,
        help="Minimum severity to report (default: all)",
    )
    parser.add_argument(
        "--no-entropy",
        action="store_true",
        help="Disable Shannon entropy analysis (faster, more false-negative risk)",
    )
    parser.add_argument(
        "--entropy-threshold",
        type=float,
        metavar="N",
        help="Override entropy threshold (default: 4.5 for base64, 3.2 for hex)",
    )
    parser.add_argument(
        "--baseline", "-b",
        metavar="FILE",
        help="JSON baseline file of known/accepted findings (fingerprints to suppress)",
    )
    parser.add_argument(
        "--fail-on",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default="CRITICAL",
        help="Exit code 2 if any findings at this severity or above (default: CRITICAL)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour output",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print scan progress and skipped files",
    )
    return parser.parse_args()


def load_baseline(path: str) -> set:
    """Return a set of fingerprints to suppress from reporting."""
    try:
        with open(path) as f:
            data = json.load(f)
        return set(data.get("accepted_fingerprints", []))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] Could not load baseline {path}: {e}", file=sys.stderr)
        return set()


def main():
    args = parse_args()

    # Pretty banner (terminal only, not when piping)
    if args.format == "terminal" and sys.stdout.isatty():
        print(BANNER)

    target = os.path.abspath(args.target)
    if not os.path.exists(target):
        print(f"[ERROR] Target does not exist: {target}", file=sys.stderr)
        sys.exit(3)

    if args.verbose:
        print(f"[*] Scanning: {target}", file=sys.stderr)
        print(f"[*] Entropy analysis: {'disabled' if args.no_entropy else 'enabled'}", file=sys.stderr)

    # ── Run scan ─────────────────────────────────────────────────────────────
    detector = SecretDetector(
        root=target,
        enable_entropy=not args.no_entropy,
        entropy_threshold=args.entropy_threshold,
        severity_filter=args.severity,
    )
    findings, stats = detector.scan()

    # ── Apply baseline suppression ───────────────────────────────────────────
    if args.baseline:
        baseline_fps = load_baseline(args.baseline)
        before = len(findings)
        findings = [f for f in findings if f.fingerprint not in baseline_fps]
        suppressed = before - len(findings)
        if suppressed and args.verbose:
            print(f"[*] Suppressed {suppressed} baseline finding(s)", file=sys.stderr)

    # ── Generate report ──────────────────────────────────────────────────────
    fmt = args.format
    if fmt == "terminal":
        output = report_terminal(findings, stats, no_color=args.no_color)
    elif fmt == "json":
        output = report_json(findings, stats, scan_root=target)
    elif fmt == "sarif":
        output = report_sarif(findings, stats, scan_root=target)
    elif fmt == "html":
        output = report_html(findings, stats, scan_root=target)
    elif fmt == "csv":
        output = report_csv(findings, stats)
    else:
        output = report_terminal(findings, stats)

    # ── Write output ─────────────────────────────────────────────────────────
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fout:
            fout.write(output)
        if args.verbose or args.format == "terminal":
            print(f"\n[✓] Report written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # ── Exit code logic ──────────────────────────────────────────────────────
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    fail_level = severity_order.get(args.fail_on, 0)

    worst = min(
        (severity_order.get(f.severity, 9) for f in findings),
        default=99,
    )

    if findings and worst <= fail_level:
        sys.exit(2)
    elif findings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
