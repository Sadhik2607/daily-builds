"""Tests for transit_pulse.metrics, run against the deterministic demo DB
(sample_data/build_demo_db.py uses random.seed(42), so planted issues are stable)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from transit_pulse import db, metrics

DEMO_DB = Path(__file__).parent / "demo_test.sqlite3"


@pytest.fixture(scope="module")
def tables():
    subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "sample_data" / "build_demo_db.py"), str(DEMO_DB)],
        check=True,
    )
    engine = db.get_engine(str(DEMO_DB))
    yield db.load_tables(engine)
    DEMO_DB.unlink(missing_ok=True)


def test_schema_is_valid(tables):
    engine = db.get_engine(str(DEMO_DB))
    assert db.validate_schema(engine) == []


def test_demand_patterns_totals(tables):
    result = metrics.demand_patterns(tables["ridership_daily"])
    assert result["total_boardings"] > 0
    assert set(result["by_route"].keys()) == set(tables["routes"]["route_id"])
    # weekday ridership should exceed weekend ridership (planted weekend_mult = 0.45)
    assert result["weekday_vs_weekend_ratio"] > 1.0


def test_seasonal_trends_has_rolling_series(tables):
    result = metrics.seasonal_trends(tables["ridership_daily"])
    assert len(result["rolling_7d_avg_series"]) > 0
    assert len(result["monthly_totals"]) >= 1


def test_utilization_flags_planted_overcrowded_route(tables):
    result = metrics.utilization(tables["ridership_daily"], tables["routes"])
    # R1 (Downtown Express) is planted with base_demand 1.35 -> should be overcrowded or near it
    assert result["by_route_load_factor"]["R1"] > result["by_route_load_factor"]["R4"]


def test_utilization_flags_planted_underused_route(tables):
    result = metrics.utilization(tables["ridership_daily"], tables["routes"])
    # R4 (Riverside Loop) is planted with base_demand 0.18 -> should land in underused
    assert "R4" in result["underused_routes"] or result["by_route_load_factor"]["R4"] < 0.3


def test_performance_indicators_flags_planted_bad_route(tables):
    result = metrics.performance_indicators(tables["service_performance"])
    # R5 (Airport Connector) is planted with a 0.74 on-time rate vs 0.93 for others
    assert result["by_route"]["R5"]["on_time_pct"] < result["by_route"]["R2"]["on_time_pct"]
    assert "R5" in result["worst_performing_routes"]


def test_route_scorecard_ranks_and_scores(tables):
    scorecard = metrics.route_scorecard(tables["ridership_daily"], tables["routes"], tables["service_performance"])
    assert len(scorecard) == len(tables["routes"])
    assert list(scorecard["score"]) == sorted(scorecard["score"], reverse=True)
    # R5's poor on-time performance should drag its score below at least one healthy route
    r5_score = scorecard.loc[scorecard["route_id"] == "R5", "score"].iloc[0]
    r2_score = scorecard.loc[scorecard["route_id"] == "R2", "score"].iloc[0]
    assert r5_score < r2_score
