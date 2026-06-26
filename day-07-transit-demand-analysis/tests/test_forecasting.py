"""Tests for transit_pulse.forecasting."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transit_pulse.forecasting import forecast_series


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(values))
    return pd.Series(values, index=idx)


def test_rising_trend_detected():
    values = [1000 + i * 40 for i in range(40)]
    result = forecast_series(_series(values), horizon_days=7)
    assert result["trend"] == "rising"
    assert result["slope_per_day"] > 0
    assert len(result["forecast"]) == 7


def test_declining_trend_detected():
    values = [3000 - i * 50 for i in range(40)]
    result = forecast_series(_series(values), horizon_days=7)
    assert result["trend"] == "declining"
    assert result["slope_per_day"] < 0


def test_flat_trend_detected():
    rng = np.random.default_rng(1)
    values = [1500 + rng.uniform(-5, 5) for _ in range(40)]
    result = forecast_series(_series(values), horizon_days=7)
    assert result["trend"] == "flat"


def test_forecast_values_never_negative():
    values = [50 - i * 5 for i in range(20)]  # would go negative if unclamped
    result = forecast_series(_series(values), horizon_days=10)
    assert all(v >= 0 for v in result["forecast"].values())


def test_insufficient_data_handled():
    result = forecast_series(_series([100, 110]), horizon_days=5)
    assert result["trend"] == "insufficient_data"
    assert result["forecast"] == {}
