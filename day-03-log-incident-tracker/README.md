# 🔍 LogSentinel — Log Parser & Incident Tracker

> Parse structured and unstructured logs, extract error patterns, calculate MTTR/MTTF, generate incident reports, and fire Slack/webhook alerts — all from a single CLI.

[![CI](https://github.com/Sadhik2607/daily-builds/actions/workflows/day-03-ci.yml/badge.svg)](https://github.com/Sadhik2607/daily-builds/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What It Does

LogSentinel ingests logs from **Apache, NGINX, Python apps, JSON-structured services, and syslog** and produces actionable incident intelligence:

| Capability | Detail |
|---|---|
| **Multi-format parsing** | Apache CLF, NGINX error, Python tracebacks, JSONL, syslog |
| **Pattern library** | 40+ error signatures with severity mapping (CRITICAL → INFO) |
| **Incident clustering** | Groups related errors within configurable time windows |
| **SRE metrics** | MTTR, MTTF, MTBF, incident rate, error rate per minute |
| **Multi-format output** | Terminal (colour), JSON, HTML report, CSV — all from one run |
| **Slack/webhook alerts** | Fires alerts when new incidents exceed configurable thresholds |
| **Azure integration** | Terraform provisions Log Analytics Workspace + alert rules |
| **GitHub Actions gate** | CI runs parser against sample logs and fails on regressions |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LogSentinel CLI                         │
│                    log-sentinel [OPTIONS] FILE                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────▼───────────────┐
           │         Parser Engine          │
           │  Apache │ NGINX │ Python │ ... │
           └───────────────┬───────────────┘
                           │  LogEntry stream
           ┌───────────────▼───────────────┐
           │       Pattern Matcher          │
           │  40+ signatures · entropy      │
           └───────────────┬───────────────┘
                           │  Matched events
           ┌───────────────▼───────────────┐
           │      Incident Clusterer        │
           │  time-window · dedup · score   │
           └───────────────┬───────────────┘
                           │  Incidents
           ┌───────────────▼───────────────┐
           │       SRE Metrics Engine       │
           │  MTTR · MTTF · MTBF · rate    │
           └───────────────┬───────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼────┐   ┌───────▼──────┐  ┌─────▼──────────┐
    │ Terminal  │   │  JSON / CSV  │  │   HTML Report   │
    │  (rich)  │   │   exports    │  │  (self-hosted)  │
    └──────────┘   └──────────────┘  └────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Notifier  │
                    │  Slack · WH │
                    └─────────────┘
```

---

## Quick Start

### Local (pip)

```bash
git clone https://github.com/Sadhik2607/daily-builds
cd daily-builds/day-03-log-incident-tracker
pip install -r requirements.txt

# Parse a sample log — terminal output
python -m log_incident_tracker.cli scan sample_data/apache_access.log

# Full report: JSON + HTML + CSV + Slack alert
python -m log_incident_tracker.cli scan sample_data/app_structured.json \
  --format all \
  --output-dir ./reports \
  --slack-webhook $SLACK_WEBHOOK_URL
```

### Docker

```bash
docker build -t logsentinel .

# Scan a log file
docker run --rm \
  -v $(pwd)/sample_data:/data \
  -v $(pwd)/reports:/reports \
  -e SLACK_WEBHOOK_URL=$SLACK_WEBHOOK_URL \
  logsentinel scan /data/app_structured.json --format all --output-dir /reports

# Tail a live log (pipe mode)
tail -f /var/log/nginx/error.log | docker run --rm -i logsentinel scan - --live
```

### Docker Compose

```bash
# Start LogSentinel + watch a directory for new logs
docker compose up
```

---

## CLI Reference

```
Usage: log-sentinel [OPTIONS] COMMAND [ARGS]...

Commands:
  scan      Parse a log file and produce incident report
  metrics   Print SRE metrics (MTTR, MTTF, MTBF) for a log file
  watch     Watch a file or directory for new log entries (tail mode)
  formats   List supported log formats and auto-detection rules

Options for `scan`:
  FILE                     Path to log file, or - for stdin
  --format [terminal|json|html|csv|all]   Output format (default: terminal)
  --output-dir DIR         Directory for file outputs (default: ./output)
  --log-type [auto|apache|nginx|python|jsonl|syslog]  Force log type
  --window SECONDS         Incident clustering window in seconds (default: 300)
  --threshold INT          Min events to declare an incident (default: 3)
  --severity [CRITICAL|ERROR|WARNING|INFO]  Minimum severity to report
  --slack-webhook URL      Slack incoming webhook URL for alerts
  --webhook URL            Generic webhook URL for alert payload
  --since DATETIME         Only process entries after this timestamp
  --top INT                Show top N error patterns (default: 10)
  --no-dedup               Disable duplicate event suppression
  --verbose                Verbose output with raw match context
```

---

## Output Examples

### Terminal

```
╔══════════════════════════════════════════════════════════╗
║        LogSentinel — Incident Report                     ║
║        Generated: 2026-06-15 09:41:22 UTC                ║
╚══════════════════════════════════════════════════════════╝

📊 Summary
  ├── Total log lines      :  48,321
  ├── Parsed successfully  :  48,291 (99.9%)
  ├── Matched events       :    1,247
  ├── Incidents detected   :       14
  └── Reporting window     : 2026-06-14 00:00 → 2026-06-15 00:00

🔴 CRITICAL  3 incidents
  INC-001  [2026-06-14 03:12]  Database connection pool exhausted (47 events, MTTR 8m 22s)
  INC-007  [2026-06-14 11:58]  OOM Killer invoked — Java heap space (12 events, MTTR 4m 01s)
  INC-012  [2026-06-14 22:31]  SSL certificate chain broken (9 events, MTTR 2m 45s)

🟠 ERROR    8 incidents
  ...

🟡 WARNING  3 incidents
  ...

⚙️  SRE Metrics
  MTTR   :   5m 03s     (Mean Time To Recovery)
  MTTF   :  98m 14s     (Mean Time To Failure)
  MTBF   : 103m 17s     (Mean Time Between Failures)
  Rate   :   0.61 incidents/hour
```

### JSON (excerpt)

```json
{
  "generated_at": "2026-06-15T09:41:22Z",
  "summary": {
    "total_lines": 48321,
    "parsed": 48291,
    "matched_events": 1247,
    "incidents": 14
  },
  "sre_metrics": {
    "mttr_seconds": 303,
    "mttf_seconds": 5894,
    "mtbf_seconds": 6197,
    "incident_rate_per_hour": 0.61
  },
  "incidents": [
    {
      "id": "INC-001",
      "severity": "CRITICAL",
      "first_seen": "2026-06-14T03:12:17Z",
      "last_seen": "2026-06-14T03:20:39Z",
      "event_count": 47,
      "pattern": "database_connection_exhausted",
      "mttr_seconds": 502,
      "sample_line": "ERROR: connection pool exhausted after 30s (pool_size=10)"
    }
  ]
}
```

---

## Supported Log Formats

| Format | Auto-detect rule | Example source |
|---|---|---|
| Apache CLF | Matches `"GET /... HTTP/` pattern | Apache HTTPD |
| NGINX error | Starts with `[YYYY/MM/DD HH:MM:SS]` | NGINX |
| Python app | Contains `Traceback (most recent call last)` | Python logging |
| JSONL | Each line is valid JSON with `timestamp`/`level` | Structured apps |
| syslog | Matches RFC 3164 / RFC 5424 | Linux syslog / rsyslog |
| CloudWatch | JSON with `logEvents[].message` key | AWS CloudWatch |

---

## Terraform — Azure Log Analytics

Provisions an Azure Log Analytics Workspace and configures alert rules that fire when error rate exceeds thresholds.

```bash
cd terraform
terraform init
terraform plan -var="resource_group=rg-logsentinel-dev"
terraform apply
```

Resources created:
- `azurerm_log_analytics_workspace` — ingests log data via Diagnostic Settings
- `azurerm_monitor_scheduled_query_rules_alert_v2` — CRITICAL incident threshold alert
- `azurerm_monitor_action_group` — email + webhook action group
- `azurerm_application_insights` — optional APM integration

---

## Slack Alert Example

When an incident breaches the threshold, LogSentinel posts to Slack:

```
🚨 [CRITICAL] LogSentinel Incident Alert
Incident INC-001 · database_connection_exhausted
First seen: 2026-06-14 03:12 UTC | Events: 47
MTTR so far: 8m 22s
Host: prod-api-03 · Log: /var/log/app/api.log
→ https://github.com/Sadhik2607/daily-builds/tree/main/day-03-log-incident-tracker
```

---

## GitHub Actions

The CI workflow runs on every push and PR:

1. Installs dependencies
2. Runs parser against all `sample_data/` files
3. Asserts known incident counts match expectations (regression gate)
4. Runs `pytest` unit tests
5. Builds Docker image and verifies it runs

---

## Roles Targeted

| Role | Value |
|---|---|
| **Ops / SRE** | Automated incident detection, MTTR/MTTF, Slack alerts |
| **BA / BSA** | HTML/CSV reports ready for stakeholder delivery |
| **Data** | Structured JSONL output consumable by BI tools |
| **DevOps** | GitHub Actions gate, Docker, Terraform IaC |

---

## License

MIT
