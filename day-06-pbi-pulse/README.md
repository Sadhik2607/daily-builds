# PBI-Pulse — Power BI Workspace & Dataset Health Monitor

Automated health checks for Power BI workspaces: catches failed/stale dataset
refreshes before stakeholders notice a stale report, and ships the result as
a terminal summary, JSON, CSV, and an HTML report you can hand to a BI lead.

Built against the real **Power BI REST API** (`/v1.0/myorg/groups`,
`.../datasets`, `.../datasets/{id}/refreshes`) using a Service Principal
(MSAL client-credentials flow) — the same auth pattern used in production
BI pipelines. Ships with a `--demo` mode backed by sample data so it runs
with zero Azure setup.

## Architecture

```
                 ┌────────────────────┐
                 │   Azure AD App      │
                 │ (Service Principal) │
                 └─────────┬───────────┘
                            │ client credentials (MSAL)
                            ▼
 ┌──────────────┐   ┌───────────────────┐   ┌────────────────────┐
 │ pbi_pulse.cli │──▶│ pbi_pulse.client  │──▶│ Power BI REST API   │
 │ (Click CLI)   │   │ (HTTP + retries)  │   │ api.powerbi.com     │
 └──────┬────────┘   └─────────┬─────────┘   └────────────────────┘
        │                      │
        ▼                      ▼
 ┌──────────────┐     ┌──────────────────┐
 │ pbi_pulse.    │◀───│ workspaces +      │
 │ monitor       │     │ datasets + refresh│
 │ (health rules)│     │ history          │
 └──────┬────────┘     └──────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────┐
 │ pbi_pulse.reporters                          │
 │  terminal | report.json | report.csv | .html │
 └─────────────────────────────────────────────┘
```

## Health rules

| Check | Trigger | Severity |
|---|---|---|
| Refresh failed | Latest refresh `status == Failed` | CRITICAL |
| Refresh stale | No successful refresh in > `--max-age-hours` (default 26h) | WARNING |
| Long-running refresh | Last refresh duration > `--max-duration-min` (default 60m) | WARNING |
| Refresh disabled | Dataset has no configured schedule and isn't refresh-on-demand only | INFO |

Each dataset gets a 0-100 health score (`100 - 40*critical - 15*warning - 5*info`, floored at 0).

## Quick start

```bash
git clone https://github.com/Sadhik2607/daily-builds.git
cd daily-builds/day-06-pbi-pulse
pip install -r requirements.txt

# Demo mode — no Azure credentials needed, runs against bundled sample data
python -m pbi_pulse.cli scan --demo --out reports/

# Real tenant — Service Principal with a Power BI Admin API/dataset read scope
export PBI_TENANT_ID=...
export PBI_CLIENT_ID=...
export PBI_CLIENT_SECRET=...
python -m pbi_pulse.cli scan --out reports/
```

### Docker

```bash
docker build -t pbi-pulse .
docker run --rm -v $(pwd)/reports:/app/reports pbi-pulse scan --demo --out reports/
```

## CLI reference

```
pbi_pulse scan [OPTIONS]

Options:
  --demo                  Use bundled sample_data/ instead of live API calls
  --workspace TEXT         Filter to one workspace (group) name, repeatable
  --max-age-hours INTEGER  Staleness threshold in hours          [default: 26]
  --max-duration-min INTEGER  Long-refresh threshold in minutes  [default: 60]
  --out PATH               Output directory for json/csv/html   [default: ./reports]
  --fail-under INTEGER     Exit code 1 if any dataset health score < N
  --webhook TEXT           POST a summary to this URL (Teams/Slack incoming webhook)
```

## Output examples

Terminal:

```
PBI-Pulse — scanned 3 workspaces, 7 datasets in 1.4s
────────────────────────────────────────────────────────────
[CRITICAL] Sales Analytics / Daily Revenue Model   score=20
   - Refresh failed: "DataSource.Error: ODBC: connection timeout"
[WARNING]  Sales Analytics / Regional Forecast     score=70
   - Refresh stale: last success 31.2h ago (threshold 26h)
[OK]       Ops Reporting / SLA Dashboard           score=100
────────────────────────────────────────────────────────────
2 issues found across 7 datasets. Reports written to ./reports/
```

`report.json` (excerpt):

```json
{
  "scanned_at": "2026-06-26T08:00:00Z",
  "datasets": [
    {
      "workspace": "Sales Analytics",
      "dataset": "Daily Revenue Model",
      "health_score": 20,
      "issues": [
        {"rule": "refresh_failed", "severity": "CRITICAL",
         "detail": "DataSource.Error: ODBC: connection timeout"}
      ]
    }
  ]
}
```

`report.csv` columns: `workspace,dataset,health_score,severity,rule,detail,last_refresh_end`

`report.html` — single-file, dependency-free dashboard with a sortable table
and a status-color column, suitable for emailing to a BI stakeholder.

## GitHub Actions

`.github/workflows/pbi-pulse.yml` runs the scan on a schedule (default: every
weekday at 13:00 UTC) and on manual dispatch, uploads `report.html`/`.json`/
`.csv` as a build artifact, and fails the job if `--fail-under 50` trips —
so a broken refresh shows up as a red check, not a surprised stakeholder.

## Tests

```bash
pytest tests/ -v
```

## Roles this targets

Power BI / BI Analyst, Data Analyst, BSA/BA (stakeholder-facing HTML/CSV
reports), and DevOps/Ops (scheduled monitoring + webhook alerting).
