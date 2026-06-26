# TransitPulse — Transit Demand & Performance Analysis

Analyzes public transit ridership and service-performance data to surface demand
patterns, seasonal trends, utilization (load factor), and operational performance
indicators across routes and time periods — with a lightweight ridership forecast
and a route scorecard, output as a terminal report, JSON, CSV, or a self-contained
HTML dashboard.

Built as Day 7 of a daily-builds series. Targets the analytical workflow behind a
Power BI / Tableau transit operations dashboard, without requiring a BI license:
the metrics, trend forecast, and route scorecard here are the same numbers that
would feed those dashboards.

## Why

Transit agencies and operations teams need to answer: which routes are overcrowded,
which are underused, which are chronically late, is ridership growing or shrinking,
and how does demand differ on weekdays vs weekends or peak vs off-peak. TransitPulse
turns raw ridership and on-time/completion data into those answers in one command.

## Architecture

```
                 ┌─────────────────────┐
                 │   Data Source       │
                 │  SQLite / Oracle /  │
                 │  Postgres / MySQL   │
                 │  (via SQLAlchemy)   │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │      db.py          │
                 │  schema validation  │
                 │  table loading      │
                 └──────────┬──────────┘
                            │  pandas DataFrames
                            ▼
        ┌───────────────────┴────────────────────┐
        ▼                                         ▼
┌───────────────────┐                  ┌─────────────────────┐
│    metrics.py      │                  │   forecasting.py    │
│ demand patterns     │                  │ linear-trend         │
│ seasonal trends     │                  │ ridership projection  │
│ utilization/load     │                  └─────────────────────┘
│ performance KPIs     │
│ route scorecard       │
└──────────┬───────────┘
           │
           ▼
 ┌──────────────────────┐
 │     reporters.py       │
 │ terminal (rich)         │
 │ JSON / CSV               │
 │ HTML (inline SVG charts)  │
 └──────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build the demo database (SQLite, deterministic synthetic data with planted issues)
python sample_data/build_demo_db.py sample_data/demo.sqlite3

# 3. Run the analysis
python -m transit_pulse.cli analyze sample_data/demo.sqlite3 --format all --output-dir ./reports
```

Or with Docker:

```bash
docker compose up --build
```

## CLI Reference

```
transit-pulse analyze <DSN> [OPTIONS]

  --format [terminal|json|html|csv|all]   Output format (default: terminal)
  --output-dir PATH                       Where to write reports (default: ./reports)
  --forecast-days INTEGER                 Days ahead to project ridership (default: 14)
  --fail-under FLOAT                      Exit 1 if system on-time % falls below this (CI gate)

transit-pulse routes <DSN>
  List all routes with their basic attributes.
```

`DSN` accepts a bare SQLite file path, a full `sqlite:///` URL, or any SQLAlchemy
URL — e.g. `oracle+oracledb://user:pass@host:1521/?service_name=XEPDB1` for an
Oracle target, or `postgresql://user:pass@host/db`.

## Data Model

Three input tables (see `sample_data/build_demo_db.py` for the demo schema):

| Table | Columns |
|---|---|
| `routes` | `route_id, route_name, mode, region, capacity_per_trip` |
| `ridership_daily` | `date, route_id, period, boardings, alightings, trips_operated` |
| `service_performance` | `date, route_id, scheduled_trips, completed_trips, on_time_trips, avg_delay_minutes` |

## Metrics

- **Demand patterns** — total/route-level boardings, ridership by day-of-week, ridership by time-of-day period, weekday-vs-weekend ratio
- **Seasonal trends** — monthly totals, month-over-month % change, 7-day rolling average series
- **Utilization** — load factor (boardings ÷ capacity offered) overall, by route, peak vs off-peak; flags routes over 0.9 (overcrowded) and under 0.25 (underused)
- **Performance indicators** — on-time %, completion rate, average delay, worst-performing routes
- **Forecast** — linear-trend projection of daily ridership N days ahead, classified rising/declining/flat
- **Route scorecard** — single ranked 0–100 score per route, weighted 35% utilization-balance + 45% on-time % + 20% completion rate

## Output Examples

**Terminal** — rich-formatted summary + ranked route scorecard table, with overcrowded/underused routes called out in red/yellow.

**JSON** (`reports/report.json`) — full metrics payload plus the route scorecard, for piping into other tools.

**CSV** (`reports/route_scorecard.csv`) — just the ranked scorecard, for spreadsheets.

**HTML** (`reports/report.html`) — single-file dashboard (no JS/CDN dependency) with summary cards, a ridership-by-route bar chart, a 30-day rolling average + forecast line chart, and the full scorecard table. Safe to email or attach.

## Testing

```bash
pip install -r requirements-dev.txt
pytest -v --cov=transit_pulse tests/
```

Tests run against the same deterministic demo database (seeded `random.seed(42)`)
and assert against its planted issues: an overcrowded route, an underused route,
and a chronically late route, plus forecast trend detection on synthetic rising/
declining/flat series.

## CI

`.github/workflows/ci.yml` builds the demo database, runs the test suite, runs the
full analysis in all output formats, gates the build on a minimum on-time %
threshold, and uploads the generated reports as build artifacts.

## Roles This Targets

| Role | Relevance |
|---|---|
| Transit / Operations Analyst | Demand, utilization, and on-time KPIs per route |
| BI / Data Analyst | Forecasting indicator + dashboard output mirrors Power BI/Tableau deliverables |
| Data Engineer | Multi-dialect SQL ingestion (SQLite/Oracle/Postgres/MySQL via SQLAlchemy) |
| Service Planning | Overcrowded/underused route flags inform schedule and capacity changes |

## Stack

Python, pandas, NumPy, SQLAlchemy (SQLite / Oracle / PostgreSQL / MySQL), Click, Rich, pytest, Docker, GitHub Actions.
