# 🛡️ QueryGuard — SQL Schema & Query Performance Auditor

Connects to a real database (SQLite or PostgreSQL), introspects the live schema, runs a
rules engine against it, EXPLAINs your real queries to catch full table scans, and produces
a report your team can actually act on — in terminal, JSON, HTML, or CSV.

## What It Does

| Capability | Detail |
|---|---|
| Schema introspection | Tables, columns, types, primary keys, foreign keys, indexes, row counts |
| Rules engine | 7 checks: missing PKs, unindexed FKs, duplicate indexes, nullable FKs, loosely-typed columns, large tables with zero indexes, empty tables |
| Query plan analysis | Runs `EXPLAIN` / `EXPLAIN QUERY PLAN` against a list of real queries, flags full table scans / sequential scans |
| Multi-engine | SQLite (zero setup) and PostgreSQL (via DSN) |
| Multi-format output | Terminal (rich, colour-coded), JSON, HTML (stakeholder-ready), CSV |
| CI gate | `--fail-on CRITICAL\|HIGH\|MEDIUM\|LOW` makes it a real regression gate in GitHub Actions |
| Docker | `Dockerfile` + `docker-compose.yml` with a live Postgres service for the full demo stack |

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      QueryGuard CLI                         │
│            queryguard scan [DSN] [OPTIONS]                  │
└───────────────────────────┬───────────────────────────────-┘
                             │
              ┌──────────────▼──────────────┐
              │   Schema Introspection       │
              │  SQLite PRAGMA · pg_catalog  │
              └──────────────┬──────────────-┘
                             │ schema model
              ┌──────────────▼──────────────┐
              │      Rules Engine            │
              │ 7 checks · severity scoring  │
              └──────────────┬──────────────-┘
                             │ findings
        ┌────────────────────┼────────────────────┐
        │                    │                     │
┌───────▼──────┐   ┌─────────▼────────┐   ┌────────▼───────┐
│   Terminal     │   │   JSON / CSV     │   │  HTML Report   │
│   (rich)       │   │   exports        │   │ (self-hosted)  │
└────────────────┘   └──────────────────┘   └────────────────┘

              ┌──────────────────────────────┐
              │   Query Plan Analyzer         │
              │  EXPLAIN against sample SQL   │
              │  flags Seq Scan / SCAN TABLE  │
              └──────────────────────────────-┘
```

## Quick Start

### Local (pip)

```bash
git clone https://github.com/Sadhik2607/daily-builds
cd daily-builds/day-04-queryguard
pip install -r requirements.txt

# Build the demo SQLite database (planted issues for the demo)
python sample_data/build_demo_db.py sample_data/demo.sqlite3

# Full report: terminal + JSON + HTML + CSV
python -m queryguard.cli scan sample_data/demo.sqlite3 \
  --queries sample_data/sample_queries.sql \
  --format all \
  --output-dir ./reports

# Use it as a CI gate
python -m queryguard.cli scan sample_data/demo.sqlite3 --fail-on HIGH
```

### Against PostgreSQL

```bash
python -m queryguard.cli scan "postgresql://user:pass@localhost:5432/mydb" \
  --queries my_queries.sql --format html
```

### Docker Compose (full stack: real Postgres + QueryGuard)

```bash
docker compose up -d postgres
docker compose run --rm queryguard scan postgresql://qg:qg@postgres:5432/qgdemo --format all --output-dir /reports
```

## CLI Reference

```
Usage: queryguard [OPTIONS] COMMAND [ARGS]...

Commands:
  scan     Scan a DSN for schema + query issues
  tables   List tables, row counts, index/FK counts for a DSN

Options for `scan`:
  DSN                              sqlite file path or postgresql:// URL
  --queries PATH                   .sql file of queries to EXPLAIN
  --format [terminal|json|html|csv|all]   Output format (default: terminal)
  --output-dir DIR                 Directory for file outputs (default: ./reports)
  --fail-on [CRITICAL|HIGH|MEDIUM|LOW|never]   Exit 1 if findings at/above this severity exist
```

## Output Examples

### Terminal

```
────────────────────── QueryGuard — Schema & Query Audit ───────────────────────
Engine: sqlite  ·  Tables scanned: 5

 Severity   Table         Column        Issue                          Recommendation
 HIGH       orders        customer_id   FK has no supporting index     CREATE INDEX ON orders(customer_id)
 HIGH       order_items   -             No primary key                 Add a PRIMARY KEY
 MEDIUM     audit_log     -             52000 rows, zero indexes       Add an index on your common filter column
 MEDIUM     order_items   order_id      Duplicate index                DROP INDEX ix_order_items_order_id_dup
 LOW        shipments     order_id      Nullable FK                    Confirm NULL is intentional

11 schema findings, 2 critical/high.

 Severity   Query                                            Result
 HIGH       SELECT * FROM orders WHERE customer_id = 42       Full table scan detected (no index used)
 HIGH       SELECT * FROM audit_log WHERE actor = '...'        Full table scan detected (no index used)
```

### JSON (excerpt)

```json
{
  "generated_at": "2026-06-16T22:49:42Z",
  "engine": "sqlite",
  "table_count": 5,
  "summary": { "finding_count": 11, "critical_high": 2 },
  "findings": [
    {
      "rule_id": "PERF001",
      "severity": "HIGH",
      "table": "orders",
      "column": "customer_id",
      "message": "Foreign key 'customer_id' -> customers.id has no supporting index.",
      "recommendation": "CREATE INDEX ON orders(customer_id) — joins and FK cascade deletes will full-scan without it."
    }
  ]
}
```

### HTML

Self-contained dark-themed report with severity-coloured chips, summary cards, schema
findings table, and query plan table — built to be emailed or linked to a stakeholder
without setting anything up.

## Rules Catalog

| Rule ID | Severity | Trigger |
|---|---|---|
| SCHEMA001 | HIGH | Table has no primary key |
| PERF001 | HIGH | Foreign key column has no supporting index |
| PERF002 | MEDIUM | Two indexes cover the exact same column set |
| PERF003 | MEDIUM | Table has >1000 rows and zero indexes |
| SCHEMA002 | LOW | Foreign key column is nullable |
| SCHEMA003 | LOW | Short-looking field stored as unconstrained TEXT/BLOB |
| INFO001 | INFO | Table has zero rows |

## Sample Data

`sample_data/schema.sql` defines a deliberately imperfect e-commerce schema (customers,
orders, order_items, shipments, audit_log) with 6 planted issues so every rule has
something to catch. `sample_data/build_demo_db.py` seeds it with ~64k rows, including a
52,000-row `audit_log` table with zero indexes — the kind of table that silently full-scans
in production until someone notices the dashboard is slow.

## GitHub Actions

CI (`.github/workflows/ci.yml`) on every push:

1. Builds the demo SQLite database
2. Runs the pytest regression suite (asserts each rule fires on the known planted issues)
3. Runs QueryGuard against the demo DB in all 4 formats and uploads the reports as a build artifact
4. Fails the build if any `CRITICAL` finding is present (CI gate demo)
5. Builds the Docker image and smoke-tests it

## Roles Targeted

| Role | Value |
|---|---|
| Data / Data Engineer | Connects to a real DB engine, structured JSON output for downstream pipelines |
| DBA / Backend | Catches missing indexes and PK gaps before they hit production |
| DevOps | GitHub Actions regression gate, Docker, CI artifact upload |
| BA / BSA | HTML/CSV reports ready for stakeholder delivery |

## License

MIT
