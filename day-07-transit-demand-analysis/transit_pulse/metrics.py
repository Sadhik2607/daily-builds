"""Demand, utilization, and operational performance metrics.

Operates on three input DataFrames:
  routes              : route_id, route_name, mode, region, capacity_per_trip
  ridership_daily      : date, route_id, period, boardings, alightings, trips_operated
  service_performance  : date, route_id, scheduled_trips, completed_trips,
                          on_time_trips, avg_delay_minutes
"""
from __future__ import annotations

import pandas as pd

PEAK_PERIODS = {"AM_PEAK", "PM_PEAK"}


def demand_patterns(ridership: pd.DataFrame) -> dict:
    """Ridership broken down by route, day-of-week, and time-of-day period."""
    df = ridership.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["dow"] = df["date"].dt.day_name()

    by_route = (
        df.groupby("route_id")["boardings"].sum().sort_values(ascending=False)
    )
    by_dow = (
        df.groupby("dow")["boardings"]
        .mean()
        .reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    )
    by_period = df.groupby("period")["boardings"].mean().sort_values(ascending=False)

    return {
        "total_boardings": int(df["boardings"].sum()),
        "by_route": by_route.to_dict(),
        "by_day_of_week": {k: round(float(v), 1) for k, v in by_dow.dropna().items()},
        "by_period": {k: round(float(v), 1) for k, v in by_period.items()},
        "weekday_vs_weekend_ratio": _weekday_weekend_ratio(df),
    }


def _weekday_weekend_ratio(df: pd.DataFrame) -> float:
    weekday = df[~df["dow"].isin(["Saturday", "Sunday"])]["boardings"].mean()
    weekend = df[df["dow"].isin(["Saturday", "Sunday"])]["boardings"].mean()
    if not weekend or pd.isna(weekend) or weekend == 0:
        return float("nan")
    return round(float(weekday / weekend), 2)


def seasonal_trends(ridership: pd.DataFrame) -> dict:
    """Month-over-month ridership trend and a 7-day rolling average series."""
    df = ridership.copy()
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date")["boardings"].sum().sort_index()

    monthly = daily.resample("MS").sum()
    mom_pct = monthly.pct_change().fillna(0) * 100

    rolling_7d = daily.rolling(7, min_periods=1).mean()

    return {
        "monthly_totals": {d.strftime("%Y-%m"): int(v) for d, v in monthly.items()},
        "month_over_month_pct": {d.strftime("%Y-%m"): round(float(v), 1) for d, v in mom_pct.items()},
        "rolling_7d_avg_series": {d.strftime("%Y-%m-%d"): round(float(v), 1) for d, v in rolling_7d.items()},
    }


def utilization(ridership: pd.DataFrame, routes: pd.DataFrame) -> dict:
    """Load factor (boardings / capacity offered) overall, by route, peak vs off-peak."""
    df = ridership.merge(routes[["route_id", "capacity_per_trip"]], on="route_id", how="left")
    df["capacity_offered"] = df["trips_operated"] * df["capacity_per_trip"]
    df["load_factor"] = df["boardings"] / df["capacity_offered"].replace(0, pd.NA)

    by_route = df.groupby("route_id")["load_factor"].mean().sort_values(ascending=False)

    df["is_peak"] = df["period"].isin(PEAK_PERIODS)
    peak_avg = df[df["is_peak"]]["load_factor"].mean()
    offpeak_avg = df[~df["is_peak"]]["load_factor"].mean()

    overcrowded = by_route[by_route > 0.9].to_dict()
    underused = by_route[by_route < 0.25].to_dict()

    return {
        "overall_avg_load_factor": round(float(df["load_factor"].mean()), 3),
        "by_route_load_factor": {k: round(float(v), 3) for k, v in by_route.items()},
        "peak_avg_load_factor": round(float(peak_avg), 3) if pd.notna(peak_avg) else None,
        "offpeak_avg_load_factor": round(float(offpeak_avg), 3) if pd.notna(offpeak_avg) else None,
        "overcrowded_routes": {k: round(float(v), 3) for k, v in overcrowded.items()},
        "underused_routes": {k: round(float(v), 3) for k, v in underused.items()},
    }


def performance_indicators(perf: pd.DataFrame) -> dict:
    """On-time performance, completion rate, and delay metrics, overall and by route."""
    df = perf.copy()
    df["on_time_pct"] = df["on_time_trips"] / df["completed_trips"].replace(0, pd.NA)
    df["completion_rate"] = df["completed_trips"] / df["scheduled_trips"].replace(0, pd.NA)

    by_route = df.groupby("route_id").agg(
        on_time_pct=("on_time_pct", "mean"),
        completion_rate=("completion_rate", "mean"),
        avg_delay_minutes=("avg_delay_minutes", "mean"),
    )

    worst_routes = by_route.sort_values("on_time_pct").head(5)

    return {
        "overall_on_time_pct": round(float(df["on_time_pct"].mean()) * 100, 1),
        "overall_completion_rate": round(float(df["completion_rate"].mean()) * 100, 1),
        "overall_avg_delay_minutes": round(float(df["avg_delay_minutes"].mean()), 1),
        "by_route": {
            r: {
                "on_time_pct": round(float(v["on_time_pct"]) * 100, 1),
                "completion_rate": round(float(v["completion_rate"]) * 100, 1),
                "avg_delay_minutes": round(float(v["avg_delay_minutes"]), 1),
            }
            for r, v in by_route.iterrows()
        },
        "worst_performing_routes": list(worst_routes.index),
    }


def route_scorecard(ridership: pd.DataFrame, routes: pd.DataFrame, perf: pd.DataFrame) -> pd.DataFrame:
    """Single ranked table: demand + utilization + performance per route, 0-100 score."""
    demand = ridership.groupby("route_id")["boardings"].sum().rename("total_boardings")
    util = utilization(ridership, routes)["by_route_load_factor"]
    perf_metrics = performance_indicators(perf)["by_route"]

    rows = []
    for route_id in routes["route_id"]:
        lf = util.get(route_id, 0) or 0
        p = perf_metrics.get(route_id, {"on_time_pct": 0, "completion_rate": 0, "avg_delay_minutes": 0})
        # Score: balanced utilization (closer to 0.7 ideal) + on-time performance + completion rate
        utilization_score = max(0, 100 - abs(lf - 0.7) * 100)
        score = round(0.35 * utilization_score + 0.45 * p["on_time_pct"] + 0.20 * p["completion_rate"], 1)
        rows.append(
            {
                "route_id": route_id,
                "total_boardings": int(demand.get(route_id, 0)),
                "load_factor": round(lf, 3),
                "on_time_pct": p["on_time_pct"],
                "completion_rate": p["completion_rate"],
                "avg_delay_minutes": p["avg_delay_minutes"],
                "score": score,
            }
        )
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
