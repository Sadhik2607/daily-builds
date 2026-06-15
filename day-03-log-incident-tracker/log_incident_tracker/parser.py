"""
Multi-format log parser.

Supports: Apache CLF, NGINX error, Python app logs, JSONL structured,
          syslog (RFC 3164 / 5424), and plain-text fallback.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional


# ── Severity constants ───────────────────────────────────────────────────────
CRITICAL = "CRITICAL"
ERROR    = "ERROR"
WARNING  = "WARNING"
INFO     = "INFO"

# ── Log type enum ────────────────────────────────────────────────────────────

class LogType(str, Enum):
    APACHE = "apache"
    NGINX  = "nginx"
    PYTHON = "python"
    JSONL  = "jsonl"
    SYSLOG = "syslog"
    PLAIN  = "plain"
    AUTO   = "auto"


# ── Core data structure ──────────────────────────────────────────────────────

@dataclass
class LogEntry:
    raw_line:   str
    timestamp:  Optional[datetime]
    level:      str          # CRITICAL / ERROR / WARNING / INFO / DEBUG / UNKNOWN
    message:    str
    host:       Optional[str] = None
    source:     Optional[str] = None   # file path or service name
    log_type:   LogType = LogType.PLAIN
    line_no:    int = 0
    extra:      dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "line_no":   self.line_no,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level":     self.level,
            "host":      self.host,
            "source":    self.source,
            "log_type":  self.log_type.value,
            "message":   self.message,
            "extra":     self.extra,
        }


# ── Timestamp normaliser ─────────────────────────────────────────────────────

_TS_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",   # Apache
    "%Y/%m/%d %H:%M:%S",       # NGINX
    "%b %d %H:%M:%S",          # syslog (no year)
    "%b  %d %H:%M:%S",         # syslog (single-digit day)
]

def _parse_ts(ts_str: str) -> Optional[datetime]:
    ts_str = ts_str.strip()
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


# ── Per-format parsers ───────────────────────────────────────────────────────

# Apache Combined Log Format
_APACHE_RE = re.compile(
    r'(?P<host>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<proto>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?'
)

def _parse_apache(line: str, line_no: int, source: str) -> Optional[LogEntry]:
    m = _APACHE_RE.match(line)
    if not m:
        return None
    status = int(m.group("status"))
    level = (
        ERROR    if status >= 500 else
        WARNING  if status >= 400 else
        INFO     if status >= 300 else
        INFO
    )
    ts = _parse_ts(m.group("ts"))
    msg = f'{m.group("method")} {m.group("path")} → {status}'
    return LogEntry(
        raw_line=line, timestamp=ts, level=level, message=msg,
        host=m.group("host"), source=source, log_type=LogType.APACHE,
        line_no=line_no,
        extra={"status": status, "path": m.group("path"), "method": m.group("method")},
    )


# NGINX error log
_NGINX_RE = re.compile(
    r'(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+'
    r'\[(?P<level>\w+)\]\s+(?P<pid>\d+)#\d+:\s+\*?\d*\s*(?P<msg>.+)'
)

def _parse_nginx(line: str, line_no: int, source: str) -> Optional[LogEntry]:
    m = _NGINX_RE.match(line)
    if not m:
        return None
    level_map = {"emerg": CRITICAL, "alert": CRITICAL, "crit": CRITICAL,
                 "error": ERROR, "warn": WARNING, "notice": INFO, "info": INFO, "debug": "DEBUG"}
    level = level_map.get(m.group("level").lower(), "UNKNOWN")
    return LogEntry(
        raw_line=line, timestamp=_parse_ts(m.group("ts")), level=level,
        message=m.group("msg").strip(), source=source, log_type=LogType.NGINX,
        line_no=line_no,
    )


# Python logging format: "2026-06-14 03:12:17,042 ERROR module:42 message"
_PY_RE = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+'
    r'(?P<level>CRITICAL|ERROR|WARNING|WARN|INFO|DEBUG|TRACE)\s+'
    r'(?P<msg>.+)'
)

def _parse_python(line: str, line_no: int, source: str) -> Optional[LogEntry]:
    m = _PY_RE.match(line)
    if not m:
        return None
    level = m.group("level").replace("WARN", "WARNING")
    return LogEntry(
        raw_line=line, timestamp=_parse_ts(m.group("ts")), level=level,
        message=m.group("msg").strip(), source=source, log_type=LogType.PYTHON,
        line_no=line_no,
    )


# JSONL — each line is a JSON object
def _parse_jsonl(line: str, line_no: int, source: str) -> Optional[LogEntry]:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    # Normalise common field names
    ts_raw  = (obj.get("timestamp") or obj.get("time") or obj.get("ts") or
               obj.get("@timestamp") or "")
    level   = (obj.get("level") or obj.get("severity") or obj.get("lvl") or
               obj.get("log.level") or "UNKNOWN").upper()
    msg     = (obj.get("message") or obj.get("msg") or obj.get("log") or
               json.dumps(obj))
    host    = obj.get("host") or obj.get("hostname")
    svc     = obj.get("service") or obj.get("service_name") or source
    return LogEntry(
        raw_line=line, timestamp=_parse_ts(str(ts_raw)), level=level,
        message=str(msg), host=host, source=svc, log_type=LogType.JSONL,
        line_no=line_no, extra=obj,
    )


# Syslog RFC 3164: "Jun 14 03:12:17 host proc[pid]: msg"
_SYSLOG_RE = re.compile(
    r'^(?P<ts>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+'
    r'(?P<host>\S+)\s+(?P<proc>[^\[:\s]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<msg>.+)$'
)
# Syslog priority heuristic from message content
_SYSLOG_LEVELS = {
    "emerg": CRITICAL, "alert": CRITICAL, "crit": CRITICAL,
    "err": ERROR, "error": ERROR,
    "warn": WARNING, "warning": WARNING,
    "notice": INFO, "info": INFO, "debug": "DEBUG",
}

def _parse_syslog(line: str, line_no: int, source: str) -> Optional[LogEntry]:
    m = _SYSLOG_RE.match(line)
    if not m:
        return None
    msg = m.group("msg")
    level = "INFO"
    for kw, lvl in _SYSLOG_LEVELS.items():
        if re.search(rf'\b{kw}\b', msg, re.I):
            level = lvl
            break
    return LogEntry(
        raw_line=line, timestamp=_parse_ts(m.group("ts")), level=level,
        message=msg, host=m.group("host"), source=m.group("proc"),
        log_type=LogType.SYSLOG, line_no=line_no,
    )


# Plain fallback
def _parse_plain(line: str, line_no: int, source: str) -> LogEntry:
    level = "UNKNOWN"
    for lvl in ("CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"):
        if lvl in line.upper():
            level = lvl.replace("WARN", "WARNING")
            break
    return LogEntry(
        raw_line=line, timestamp=None, level=level,
        message=line.strip(), source=source, log_type=LogType.PLAIN,
        line_no=line_no,
    )


# ── Auto-detection ────────────────────────────────────────────────────────────

def detect_log_type(sample_lines: list[str]) -> LogType:
    """Detect log format from first few non-empty lines."""
    for line in sample_lines[:20]:
        line = line.strip()
        if not line:
            continue
        if _APACHE_RE.match(line):
            return LogType.APACHE
        if _NGINX_RE.match(line):
            return LogType.NGINX
        if _PY_RE.match(line):
            return LogType.PYTHON
        if _SYSLOG_RE.match(line):
            return LogType.SYSLOG
        try:
            json.loads(line)
            return LogType.JSONL
        except json.JSONDecodeError:
            pass
    return LogType.PLAIN


# ── Public parser ─────────────────────────────────────────────────────────────

def parse_file(
    path: str | Path | None,
    log_type: LogType = LogType.AUTO,
) -> Iterator[LogEntry]:
    """
    Yield LogEntry objects from *path* (or stdin if path is None / "-").
    """
    if path is None or str(path) == "-":
        fh = sys.stdin
        source = "stdin"
    else:
        path = Path(path)
        fh = open(path, encoding="utf-8", errors="replace")
        source = str(path)

    try:
        lines = fh.readlines()
    finally:
        if fh is not sys.stdin:
            fh.close()

    if log_type == LogType.AUTO:
        log_type = detect_log_type(lines)

    _parsers = {
        LogType.APACHE: _parse_apache,
        LogType.NGINX:  _parse_nginx,
        LogType.PYTHON: _parse_python,
        LogType.JSONL:  _parse_jsonl,
        LogType.SYSLOG: _parse_syslog,
    }
    parser_fn = _parsers.get(log_type)

    for line_no, raw in enumerate(lines, start=1):
        raw = raw.rstrip("\n")
        if not raw.strip():
            continue
        entry: Optional[LogEntry] = None
        if parser_fn:
            entry = parser_fn(raw, line_no, source)
        if entry is None:
            entry = _parse_plain(raw, line_no, source)
        yield entry
