"""Unit tests for incident clustering and SRE metrics."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from log_incident_tracker.incident_tracker import (
    cluster_incidents,
    compute_sre_metrics,
    match_events,
)
from log_incident_tracker.parser import LogEntry, LogType
from log_incident_tracker.patterns import PATTERNS


def _make_entry(msg: str, ts_offset_minutes: int = 0, level: str = "ERROR") -> LogEntry:
    ts = datetime(2026, 6, 14, 3, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=ts_offset_minutes)
    return LogEntry(
        raw_line=msg,
        timestamp=ts,
        level=level,
        message=msg,
        log_type=LogType.PLAIN,
        line_no=1,
    )


class TestPatternMatching:
    def test_connection_pool_matched(self):
        entries = [_make_entry("connection pool exhausted after 30s")]
        events = match_events(entries)
        assert len(events) == 1
        assert events[0].pattern.id == "db_conn_exhausted"

    def test_ssl_error_matched(self):
        entries = [_make_entry("SSL certificate chain broken — CERTIFICATE_VERIFY_FAILED")]
        events = match_events(entries)
        assert len(events) == 1
        assert "ssl" in events[0].pattern.tags

    def test_oom_matched(self):
        entries = [_make_entry("java.lang.OutOfMemoryError: Java heap space")]
        events = match_events(entries)
        assert len(events) == 1
        assert events[0].pattern.severity == "CRITICAL"

    def test_normal_line_not_matched(self):
        entries = [_make_entry("Service started successfully")]
        events = match_events(entries)
        assert len(events) == 0

    def test_multiple_entries(self):
        entries = [
            _make_entry("connection pool exhausted"),
            _make_entry("Service started OK"),
            _make_entry("SSL certificate chain broken"),
            _make_entry("Out of memory: Kill process 4521"),
        ]
        events = match_events(entries)
        assert len(events) == 3


class TestIncidentClustering:
    def test_same_pattern_within_window_clusters(self):
        entries = [
            _make_entry("connection pool exhausted", ts_offset_minutes=0),
            _make_entry("connection pool exhausted", ts_offset_minutes=1),
            _make_entry("connection pool exhausted", ts_offset_minutes=2),
        ]
        events = match_events(entries)
        incidents = cluster_incidents(events, window_seconds=300)
        # All three should be one incident
        db_incidents = [i for i in incidents if i.pattern.id == "db_conn_exhausted"]
        assert len(db_incidents) == 1
        assert db_incidents[0].event_count == 3

    def test_pattern_outside_window_creates_new_incident(self):
        entries = [
            _make_entry("connection pool exhausted", ts_offset_minutes=0),
            _make_entry("connection pool exhausted", ts_offset_minutes=60),  # 1 hour later
        ]
        events = match_events(entries)
        incidents = cluster_incidents(events, window_seconds=300)  # 5 min window
        db_incidents = [i for i in incidents if i.pattern.id == "db_conn_exhausted"]
        assert len(db_incidents) == 2

    def test_different_patterns_produce_separate_incidents(self):
        entries = [
            _make_entry("connection pool exhausted", ts_offset_minutes=0),
            _make_entry("SSL certificate chain broken", ts_offset_minutes=1),
        ]
        events = match_events(entries)
        incidents = cluster_incidents(events, window_seconds=300)
        assert len(incidents) == 2

    def test_incident_has_correct_first_last_seen(self):
        base = datetime(2026, 6, 14, 3, 0, 0, tzinfo=timezone.utc)
        entries = [
            _make_entry("connection pool exhausted", ts_offset_minutes=0),
            _make_entry("connection pool exhausted", ts_offset_minutes=2),
            _make_entry("connection pool exhausted", ts_offset_minutes=4),
        ]
        events = match_events(entries)
        incidents = cluster_incidents(events, window_seconds=600)
        inc = incidents[0]
        assert inc.first_seen == base
        assert (inc.last_seen - base).total_seconds() == 4 * 60

    def test_min_events_threshold(self):
        entries = [_make_entry("connection pool exhausted", ts_offset_minutes=0)]
        events = match_events(entries)
        # With min_events=2, single event should NOT produce an incident
        incidents = cluster_incidents(events, min_events=2)
        assert len(incidents) == 0


class TestSREMetrics:
    def _make_incidents_list(self):
        """Create two incidents with known durations for metric testing."""
        from log_incident_tracker.incident_tracker import Incident, MatchedEvent
        from log_incident_tracker.patterns import PATTERNS

        pattern = PATTERNS[0]  # db_conn_exhausted
        t0 = datetime(2026, 6, 14, 3, 0, 0, tzinfo=timezone.utc)

        inc1 = Incident(
            id="INC-001", severity="CRITICAL", pattern=pattern,
            first_seen=t0, last_seen=t0 + timedelta(minutes=8),
        )
        inc2 = Incident(
            id="INC-002", severity="ERROR", pattern=pattern,
            first_seen=t0 + timedelta(hours=2), last_seen=t0 + timedelta(hours=2, minutes=4),
        )
        return [inc1, inc2]

    def test_mttr_calculated(self):
        incidents = self._make_incidents_list()
        entries = [
            _make_entry("x", 0),
            _make_entry("x", 180),  # 3 hours
        ]
        metrics = compute_sre_metrics(incidents, entries)
        # MTTR = (8min + 4min) / 2 = 6min = 360s
        assert metrics.mttr_seconds == pytest.approx(360.0, abs=1)

    def test_total_incidents(self):
        incidents = self._make_incidents_list()
        metrics = compute_sre_metrics(incidents, [_make_entry("x", 0)])
        assert metrics.total_incidents == 2

    def test_severity_counts(self):
        incidents = self._make_incidents_list()
        metrics = compute_sre_metrics(incidents, [_make_entry("x", 0)])
        assert metrics.critical_count == 1
        assert metrics.error_count == 1
        assert metrics.warning_count == 0

    def test_no_incidents_returns_none_mttr(self):
        metrics = compute_sre_metrics([], [_make_entry("x", 0)])
        assert metrics.mttr_seconds is None
        assert metrics.total_incidents == 0
