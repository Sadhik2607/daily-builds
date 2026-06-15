"""
Incident clustering and SRE metrics engine.

Groups matched log events into incidents using a sliding time window,
then computes MTTR, MTTF, and MTBF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .parser import LogEntry
from .patterns import Pattern, PATTERNS, CRITICAL, ERROR, WARNING, INFO


# ── Matched event ─────────────────────────────────────────────────────────────

@dataclass
class MatchedEvent:
    entry:    LogEntry
    pattern:  Pattern
    match_text: str  # the matched substring

    def as_dict(self) -> dict:
        return {
            **self.entry.as_dict(),
            "pattern_id":   self.pattern.id,
            "pattern_name": self.pattern.name,
            "severity":     self.pattern.severity,
            "category":     self.pattern.category,
            "tags":         self.pattern.tags,
            "match_text":   self.match_text,
        }


# ── Incident ──────────────────────────────────────────────────────────────────

@dataclass
class Incident:
    id:           str
    severity:     str
    pattern:      Pattern
    first_seen:   Optional[datetime]
    last_seen:    Optional[datetime]
    events:       List[MatchedEvent] = field(default_factory=list)
    resolved_at:  Optional[datetime] = None
    mttr_seconds: Optional[float] = None  # filled after full scan

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.first_seen and self.last_seen:
            return (self.last_seen - self.first_seen).total_seconds()
        return None

    @property
    def sample_line(self) -> str:
        return self.events[0].entry.raw_line if self.events else ""

    def as_dict(self) -> dict:
        return {
            "id":           self.id,
            "severity":     self.severity,
            "pattern_id":   self.pattern.id,
            "pattern_name": self.pattern.name,
            "category":     self.pattern.category,
            "tags":         self.pattern.tags,
            "first_seen":   self.first_seen.isoformat() if self.first_seen else None,
            "last_seen":    self.last_seen.isoformat() if self.last_seen else None,
            "resolved_at":  self.resolved_at.isoformat() if self.resolved_at else None,
            "event_count":  self.event_count,
            "duration_seconds": self.duration_seconds,
            "mttr_seconds": self.mttr_seconds,
            "sample_line":  self.sample_line,
        }


# ── SRE Metrics ───────────────────────────────────────────────────────────────

@dataclass
class SREMetrics:
    total_incidents: int
    mttr_seconds:    Optional[float]  # Mean Time To Recovery
    mttf_seconds:    Optional[float]  # Mean Time To Failure (first event → incident)
    mtbf_seconds:    Optional[float]  # Mean Time Between Failures
    incident_rate_per_hour: float
    observation_window_seconds: float
    critical_count:  int
    error_count:     int
    warning_count:   int

    def as_dict(self) -> dict:
        return {
            "total_incidents":        self.total_incidents,
            "mttr_seconds":           round(self.mttr_seconds, 1) if self.mttr_seconds is not None else None,
            "mttf_seconds":           round(self.mttf_seconds, 1) if self.mttf_seconds is not None else None,
            "mtbf_seconds":           round(self.mtbf_seconds, 1) if self.mtbf_seconds is not None else None,
            "incident_rate_per_hour": round(self.incident_rate_per_hour, 3),
            "observation_window_hours": round(self.observation_window_seconds / 3600, 2),
            "by_severity": {
                "CRITICAL": self.critical_count,
                "ERROR":    self.error_count,
                "WARNING":  self.warning_count,
            },
        }


# ── Engine ────────────────────────────────────────────────────────────────────

_COMPILED_PATTERNS: List[Tuple[Pattern, re.Pattern]] = [
    (p, re.compile(p.regex)) for p in PATTERNS
]

_SEVERITY_ORDER = {CRITICAL: 0, ERROR: 1, WARNING: 2, INFO: 3, "DEBUG": 4, "UNKNOWN": 5}


def match_events(entries: List[LogEntry]) -> List[MatchedEvent]:
    """Run the pattern library against each LogEntry and return matches."""
    matched: List[MatchedEvent] = []
    for entry in entries:
        for pattern, compiled in _COMPILED_PATTERNS:
            m = compiled.search(entry.raw_line)
            if m:
                # Keep the higher-severity pattern if multiple match
                matched.append(MatchedEvent(
                    entry=entry,
                    pattern=pattern,
                    match_text=m.group(0),
                ))
                break  # one pattern per line (first match wins — ordered by severity)
    return matched


def cluster_incidents(
    events: List[MatchedEvent],
    window_seconds: int = 300,
    min_events: int = 1,
) -> List[Incident]:
    """
    Group events into incidents using a sliding time window.
    Events with the same pattern_id within `window_seconds` of each other
    belong to the same incident.
    """
    # Sort by pattern_id, then timestamp
    by_pattern: Dict[str, List[MatchedEvent]] = {}
    for ev in events:
        by_pattern.setdefault(ev.pattern.id, []).append(ev)

    incidents: List[Incident] = []
    inc_counter = 0

    for pattern_id, pat_events in by_pattern.items():
        # Sort by timestamp (put None-ts events at beginning)
        timed = [e for e in pat_events if e.entry.timestamp is not None]
        untimed = [e for e in pat_events if e.entry.timestamp is None]
        timed.sort(key=lambda e: e.entry.timestamp)

        # Sliding window clustering
        current_cluster: List[MatchedEvent] = []
        window_end: Optional[datetime] = None

        def flush_cluster(cluster: List[MatchedEvent]) -> None:
            nonlocal inc_counter
            if len(cluster) < min_events:
                return
            inc_counter += 1
            first_ts = next((e.entry.timestamp for e in cluster if e.entry.timestamp), None)
            last_ts  = cluster[-1].entry.timestamp if cluster else None
            pattern  = cluster[0].pattern
            sev      = pattern.severity
            incidents.append(Incident(
                id=f"INC-{inc_counter:03d}",
                severity=sev,
                pattern=pattern,
                first_seen=first_ts,
                last_seen=last_ts,
                events=cluster[:],
            ))

        for ev in timed:
            ts = ev.entry.timestamp
            if window_end is None:
                window_end = ts + timedelta(seconds=window_seconds)
                current_cluster = [ev]
            elif ts <= window_end:
                current_cluster.append(ev)
                # Extend window on each new event
                window_end = ts + timedelta(seconds=window_seconds)
            else:
                flush_cluster(current_cluster)
                current_cluster = [ev]
                window_end = ts + timedelta(seconds=window_seconds)

        flush_cluster(current_cluster)

        # Untimed events: attach to last incident for that pattern, or create one
        if untimed:
            matching = [i for i in incidents if i.pattern.id == pattern_id]
            if matching:
                matching[-1].events.extend(untimed)
            elif len(untimed) >= min_events:
                inc_counter += 1
                pattern = untimed[0].pattern
                incidents.append(Incident(
                    id=f"INC-{inc_counter:03d}",
                    severity=pattern.severity,
                    pattern=pattern,
                    first_seen=None,
                    last_seen=None,
                    events=untimed,
                ))

    # Sort incidents by severity then first_seen
    incidents.sort(key=lambda i: (
        _SEVERITY_ORDER.get(i.severity, 99),
        i.first_seen or datetime.min.replace(tzinfo=timezone.utc),
    ))

    return incidents


def compute_sre_metrics(
    incidents: List[Incident],
    all_entries: List[LogEntry],
) -> SREMetrics:
    """
    Compute MTTR, MTTF, MTBF, and incident rate.

    MTTR: average incident duration (first → last event as proxy for recovery).
    MTTF: average time from previous incident end to next incident start.
    MTBF: MTTF + MTTR.
    """
    # Observation window from first to last log entry
    timed = [e for e in all_entries if e.timestamp]
    obs_seconds = 0.0
    if timed:
        obs_seconds = (timed[-1].timestamp - timed[0].timestamp).total_seconds()

    timed_incidents = [i for i in incidents if i.first_seen and i.last_seen]

    # MTTR: mean duration of each incident (last_seen - first_seen)
    mttr: Optional[float] = None
    if timed_incidents:
        durations = [(i.last_seen - i.first_seen).total_seconds() for i in timed_incidents]
        mttr = sum(durations) / len(durations)

    # MTTF / MTBF via inter-incident gaps
    mttf: Optional[float] = None
    mtbf: Optional[float] = None
    if len(timed_incidents) >= 2:
        gaps = []
        for a, b in zip(timed_incidents, timed_incidents[1:]):
            gap = (b.first_seen - a.last_seen).total_seconds()
            if gap > 0:
                gaps.append(gap)
        if gaps:
            mttf = sum(gaps) / len(gaps)
            mtbf = mttf + (mttr or 0)

    rate = (len(incidents) / (obs_seconds / 3600)) if obs_seconds > 0 else 0.0

    return SREMetrics(
        total_incidents=len(incidents),
        mttr_seconds=mttr,
        mttf_seconds=mttf,
        mtbf_seconds=mtbf,
        incident_rate_per_hour=rate,
        observation_window_seconds=obs_seconds,
        critical_count=sum(1 for i in incidents if i.severity == CRITICAL),
        error_count=sum(1 for i in incidents if i.severity == ERROR),
        warning_count=sum(1 for i in incidents if i.severity == WARNING),
    )
