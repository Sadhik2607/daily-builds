"""Lightweight ridership forecasting — linear trend projection over a rolling
average series. No heavyweight ML dependency; this is the same class of
"forecasting indicator" a Power BI/Tableau dashboard would show as a trend
line + projected value, not a full statistical forecasting model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def forecast_series(daily_boardings: pd.Series, horizon_days: int = 14) -> dict:
    """Fit a linear trend to the recent history and project forward.

    Args:
        daily_boardings: Series indexed by date, values = total boardings that day.
        horizon_days: how many days ahead to project.
    """
    series = daily_boardings.sort_index()
    series = series.tail(60) if len(series) > 60 else series  # recent window only

    x = np.arange(len(series))
    y = series.values.astype(float)

    if len(x) < 3:
        return {"trend": "insufficient_data", "forecast": {}}

    slope, intercept = np.polyfit(x, y, 1)
    avg = float(y.mean())
    slope_pct_of_avg = (slope / avg * 100) if avg else 0.0

    if slope_pct_of_avg > 1.5:
        trend = "rising"
    elif slope_pct_of_avg < -1.5:
        trend = "declining"
    else:
        trend = "flat"

    last_date = series.index[-1]
    future_x = np.arange(len(series), len(series) + horizon_days)
    future_y = slope * future_x + intercept
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days)

    forecast = {d.strftime("%Y-%m-%d"): round(max(0.0, float(v)), 1) for d, v in zip(future_dates, future_y)}

    return {
        "trend": trend,
        "slope_per_day": round(float(slope), 2),
        "slope_pct_of_avg_per_day": round(float(slope_pct_of_avg), 2),
        "current_avg_daily_boardings": round(avg, 1),
        "forecast": forecast,
        "horizon_days": horizon_days,
    }
