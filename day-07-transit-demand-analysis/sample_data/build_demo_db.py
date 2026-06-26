"""Builds a synthetic transit demo SQLite database with realistic, deliberately
imperfect ridership and service-performance patterns so every metric in
transit_pulse has something real to surface:

- Route 1 ("Downtown Express"): overcrowded at peak (load factor > 0.9)
- Route 4 ("Riverside Loop"): underused (load factor < 0.25)
- Route 5 ("Airport Connector"): poor on-time performance (planted delays)
- Weekday vs weekend ridership split, AM/PM peak bulges
- A seasonal dip across the synthetic "winter" window + a rising trend in the last 2 weeks

Usage:
    python sample_data/build_demo_db.py sample_data/demo.sqlite3
"""
from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

ROUTES = [
    {"route_id": "R1", "route_name": "Downtown Express", "mode": "Bus", "region": "Core", "capacity_per_trip": 60, "base_demand": 1.35},
    {"route_id": "R2", "route_name": "Harbourview", "mode": "Bus", "region": "West", "capacity_per_trip": 50, "base_demand": 0.85},
    {"route_id": "R3", "route_name": "University Line", "mode": "LRT", "region": "North", "capacity_per_trip": 180, "base_demand": 1.0},
    {"route_id": "R4", "route_name": "Riverside Loop", "mode": "Bus", "region": "East", "capacity_per_trip": 50, "base_demand": 0.18},
    {"route_id": "R5", "route_name": "Airport Connector", "mode": "Bus", "region": "South", "capacity_per_trip": 45, "base_demand": 0.7},
    {"route_id": "R6", "route_name": "Industrial Shuttle", "mode": "Bus", "region": "East", "capacity_per_trip": 40, "base_demand": 0.55},
]

PERIODS = {
    "AM_PEAK": {"trips": 6, "demand_mult": 1.6},
    "MIDDAY": {"trips": 8, "demand_mult": 0.8},
    "PM_PEAK": {"trips": 6, "demand_mult": 1.7},
    "EVENING": {"trips": 5, "demand_mult": 0.5},
}

DAYS_OF_DATA = 120
START_DATE = date.today() - timedelta(days=DAYS_OF_DATA)


def seasonal_factor(d: date) -> float:
    """Dip in the middle third of the window, gentle rise in the last 2 weeks."""
    day_index = (d - START_DATE).days
    dip = 0.85 if DAYS_OF_DATA * 0.35 < day_index < DAYS_OF_DATA * 0.65 else 1.0
    rise = 1.0 + max(0, (day_index - (DAYS_OF_DATA - 14))) * 0.012
    return dip * rise


def build(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """CREATE TABLE routes (
            route_id TEXT PRIMARY KEY, route_name TEXT, mode TEXT, region TEXT, capacity_per_trip INTEGER
        )"""
    )
    cur.execute(
        """CREATE TABLE ridership_daily (
            date TEXT, route_id TEXT, period TEXT, boardings INTEGER, alightings INTEGER, trips_operated INTEGER
        )"""
    )
    cur.execute(
        """CREATE TABLE service_performance (
            date TEXT, route_id TEXT, scheduled_trips INTEGER, completed_trips INTEGER,
            on_time_trips INTEGER, avg_delay_minutes REAL
        )"""
    )

    for r in ROUTES:
        cur.execute(
            "INSERT INTO routes VALUES (?,?,?,?,?)",
            (r["route_id"], r["route_name"], r["mode"], r["region"], r["capacity_per_trip"]),
        )

    ridership_rows = []
    perf_rows = []

    for day_offset in range(DAYS_OF_DATA):
        d = START_DATE + timedelta(days=day_offset)
        is_weekend = d.weekday() >= 5
        weekend_mult = 0.45 if is_weekend else 1.0
        season = seasonal_factor(d)

        for r in ROUTES:
            scheduled_trips_day = 0
            completed_trips_day = 0
            on_time_trips_day = 0
            delays = []

            for period, pinfo in PERIODS.items():
                trips = pinfo["trips"] if not is_weekend else max(2, pinfo["trips"] // 2)
                cap = r["capacity_per_trip"]

                demand_factor = r["base_demand"] * pinfo["demand_mult"] * weekend_mult * season
                noise = random.uniform(0.85, 1.15)
                boardings_per_trip = cap * min(demand_factor * noise, 1.4)  # allow slight overcrowding
                boardings = max(0, int(boardings_per_trip * trips))
                alightings = int(boardings * random.uniform(0.92, 1.0))

                ridership_rows.append((d.isoformat(), r["route_id"], period, boardings, alightings, trips))

                scheduled_trips_day += trips
                # Airport Connector (R5) gets planted reliability problems
                cancel_rate = 0.12 if r["route_id"] == "R5" else 0.02
                completed = sum(1 for _ in range(trips) if random.random() > cancel_rate)
                completed_trips_day += completed

                ontime_rate = 0.74 if r["route_id"] == "R5" else 0.93
                on_time = sum(1 for _ in range(completed) if random.random() < ontime_rate)
                on_time_trips_day += on_time

                avg_delay = random.uniform(6, 14) if r["route_id"] == "R5" else random.uniform(0.5, 4)
                delays.append(avg_delay)

            perf_rows.append(
                (
                    d.isoformat(),
                    r["route_id"],
                    scheduled_trips_day,
                    completed_trips_day,
                    on_time_trips_day,
                    round(sum(delays) / len(delays), 2),
                )
            )

    cur.executemany("INSERT INTO ridership_daily VALUES (?,?,?,?,?,?)", ridership_rows)
    cur.executemany("INSERT INTO service_performance VALUES (?,?,?,?,?,?)", perf_rows)

    conn.commit()
    conn.close()
    print(f"Built {db_path} — {len(ROUTES)} routes, {DAYS_OF_DATA} days, {len(ridership_rows)} ridership rows, {len(perf_rows)} performance rows.")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_data/demo.sqlite3")
    target.parent.mkdir(parents=True, exist_ok=True)
    build(target)
