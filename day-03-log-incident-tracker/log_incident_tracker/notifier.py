"""
Slack and generic webhook notifier.

Fires an alert when incidents are detected above a configurable severity threshold.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional

from .incident_tracker import Incident, SREMetrics
from .reporter import _fmt_seconds


def _build_slack_payload(
    incidents: List[Incident],
    metrics: SREMetrics,
    log_source: str,
    github_url: str = "https://github.com/Sadhik2607/daily-builds/tree/main/day-03-log-incident-tracker",
) -> dict:
    critical = [i for i in incidents if i.severity == "CRITICAL"]
    errors   = [i for i in incidents if i.severity == "ERROR"]
    warnings = [i for i in incidents if i.severity == "WARNING"]

    overall_icon = "🔴" if critical else "🟠" if errors else "🟡" if warnings else "🟢"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Header block
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{overall_icon} LogSentinel — Incident Alert"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Source:*\n`{log_source}`"},
                {"type": "mrkdwn", "text": f"*Generated:*\n{now}"},
                {"type": "mrkdwn", "text": f"*Total Incidents:*\n{len(incidents)}"},
                {"type": "mrkdwn", "text": f"*MTTR:*\n{_fmt_seconds(metrics.mttr_seconds)}"},
            ],
        },
        {"type": "divider"},
    ]

    # Top 5 incidents
    for inc in incidents[:5]:
        ts = inc.first_seen.strftime("%Y-%m-%d %H:%M UTC") if inc.first_seen else "unknown"
        icon = {"CRITICAL": "🔴", "ERROR": "🟠", "WARNING": "🟡"}.get(inc.severity, "🔵")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{icon} *{inc.id}* — {inc.pattern.name}\n"
                    f"First seen: {ts} | Events: {inc.event_count} | "
                    f"Duration: {_fmt_seconds(inc.duration_seconds)}\n"
                    f"```{inc.sample_line[:120]}```"
                ),
            },
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View on GitHub"},
                "url": github_url,
                "style": "primary",
            }
        ],
    })

    return {
        "text": f"{overall_icon} LogSentinel: {len(incidents)} incident(s) detected in `{log_source}`",
        "blocks": blocks,
    }


def _build_generic_payload(
    incidents: List[Incident],
    metrics: SREMetrics,
    log_source: str,
) -> dict:
    return {
        "source":    "logsentinel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "log_file":  log_source,
        "summary": {
            "total_incidents": len(incidents),
            "critical":        sum(1 for i in incidents if i.severity == "CRITICAL"),
            "error":           sum(1 for i in incidents if i.severity == "ERROR"),
            "warning":         sum(1 for i in incidents if i.severity == "WARNING"),
        },
        "sre_metrics": metrics.as_dict(),
        "incidents":   [i.as_dict() for i in incidents[:10]],
    }


def _post(url: str, payload: dict, timeout: int = 10) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "LogSentinel/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except urllib.error.URLError as exc:
        print(f"[notifier] webhook POST failed: {exc}")
        return False


def notify(
    incidents: List[Incident],
    metrics: SREMetrics,
    log_source: str,
    slack_webhook: Optional[str] = None,
    generic_webhook: Optional[str] = None,
    min_severity: str = "ERROR",
) -> None:
    """
    Fire Slack and/or generic webhook alerts if incidents breach min_severity.
    Reads SLACK_WEBHOOK_URL and WEBHOOK_URL from env if not provided explicitly.
    """
    slack_url   = slack_webhook   or os.environ.get("SLACK_WEBHOOK_URL")
    generic_url = generic_webhook or os.environ.get("WEBHOOK_URL")

    _order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    threshold = _order.get(min_severity, 1)
    triggering = [i for i in incidents if _order.get(i.severity, 99) <= threshold]

    if not triggering:
        return

    if slack_url:
        payload = _build_slack_payload(triggering, metrics, log_source)
        ok = _post(slack_url, payload)
        status = "✓ sent" if ok else "✗ failed"
        print(f"[notifier] Slack alert {status} ({len(triggering)} incidents)")

    if generic_url:
        payload = _build_generic_payload(triggering, metrics, log_source)
        ok = _post(generic_url, payload)
        status = "✓ sent" if ok else "✗ failed"
        print(f"[notifier] Webhook alert {status} ({len(triggering)} incidents)")
