import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from queryguard.introspect import introspect  # noqa: E402
from queryguard.rules import run_rules  # noqa: E402

DB_PATH = os.path.join(ROOT, "sample_data", "demo.sqlite3")


@pytest.fixture(scope="module", autouse=True)
def build_db():
    script = os.path.join(ROOT, "sample_data", "build_demo_db.py")
    subprocess.run([sys.executable, script, DB_PATH], check=True)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_introspect_finds_all_tables():
    schema = introspect(DB_PATH)
    assert set(schema["tables"]) == {"customers", "orders", "order_items", "shipments", "audit_log"}


def test_missing_primary_key_detected():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    assert any(f.rule_id == "SCHEMA001" and f.table == "order_items" for f in findings)


def test_unindexed_fk_detected():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    assert any(f.rule_id == "PERF001" and f.table == "orders" and f.column == "customer_id" for f in findings)


def test_duplicate_index_detected():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    assert any(f.rule_id == "PERF002" and f.table == "order_items" for f in findings)


def test_nullable_fk_detected():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    assert any(f.rule_id == "SCHEMA002" and f.table == "shipments" and f.column == "order_id" for f in findings)


def test_large_table_without_index_detected():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    assert any(f.rule_id == "PERF003" and f.table == "audit_log" for f in findings)


def test_minimum_finding_count():
    schema = introspect(DB_PATH)
    findings = run_rules(schema)
    # Regression gate: schema has 6 planted issues; fail if fewer are caught.
    assert len(findings) >= 6
