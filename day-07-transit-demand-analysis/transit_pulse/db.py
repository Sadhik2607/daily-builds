"""Database connection layer.

Supports SQLite (zero-setup demo) and Oracle (via the `oracledb` driver,
SQLAlchemy `oracle+oracledb://` dialect) — the two engines named in the
target stack. PostgreSQL/MySQL DSNs also work transparently since we go
through SQLAlchemy, but Oracle is the documented production target.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

REQUIRED_TABLES = ["routes", "ridership_daily", "service_performance"]


def get_engine(dsn: str) -> Engine:
    """Create a SQLAlchemy engine for a sqlite file path, sqlite:///, or any
    full SQLAlchemy DSN (e.g. oracle+oracledb://user:pass@host:1521/?service_name=XEPDB1).
    """
    if not dsn.startswith(("sqlite", "oracle", "postgresql", "mysql")):
        # treat bare paths as a sqlite file
        dsn = f"sqlite:///{dsn}"
    return create_engine(dsn)


def load_tables(engine: Engine) -> dict[str, pd.DataFrame]:
    """Load the three core tables into pandas DataFrames."""
    frames = {}
    for table in REQUIRED_TABLES:
        frames[table] = pd.read_sql_table(table, engine) if engine.dialect.name != "sqlite" else _sqlite_read(engine, table)
    return frames


def _sqlite_read(engine: Engine, table: str) -> pd.DataFrame:
    # pandas.read_sql_table requires a Table reflection that's flaky on some
    # sqlite/SQLAlchemy version combos — read_sql_query is more reliable here.
    return pd.read_sql_query(f"SELECT * FROM {table}", engine)


def validate_schema(engine: Engine) -> list[str]:
    """Return a list of missing required tables (empty list = schema OK)."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    return [t for t in REQUIRED_TABLES if t not in existing]
