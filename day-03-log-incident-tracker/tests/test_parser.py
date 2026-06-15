"""Unit tests for the multi-format log parser."""

import io
import sys
import textwrap
from datetime import timezone
from pathlib import Path

import pytest

# Make the package importable from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_incident_tracker.parser import (
    LogEntry, LogType, detect_log_type, parse_file
)


SAMPLE_APACHE = textwrap.dedent("""\
    192.168.1.10 - alice [14/Jun/2026:03:12:17 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
    10.0.0.1 - - [14/Jun/2026:03:12:19 +0000] "POST /api/data HTTP/1.1" 500 312 "-" "DataService/2.0"
    192.168.1.11 - bob [14/Jun/2026:03:12:21 +0000] "POST /api/login HTTP/1.1" 401 89 "-" "curl/7.81.0"
""")

SAMPLE_PYTHON = textwrap.dedent("""\
    2026-06-14 03:11:00,001 ERROR app.db: connection pool exhausted
    2026-06-14 03:11:05,200 WARNING app.db: pool pressure: 17/20 in use
    2026-06-14 03:12:00,300 CRITICAL app.jvm: java.lang.OutOfMemoryError: Java heap space
    2026-06-14 03:15:00,100 INFO  app.db: Connection pool normal
""")

SAMPLE_JSONL = textwrap.dedent("""\
    {"timestamp":"2026-06-14T03:11:00Z","level":"ERROR","service":"db","message":"connection pool exhausted","host":"prod-db-01"}
    {"timestamp":"2026-06-14T03:12:00Z","level":"CRITICAL","service":"jvm","message":"java.lang.OutOfMemoryError: Java heap space","host":"prod-worker-01"}
    {"timestamp":"2026-06-14T03:19:00Z","level":"INFO","service":"api","message":"Service recovered","host":"prod-api-01"}
""")

SAMPLE_NGINX = textwrap.dedent("""\
    2026/06/14 03:11:02 [error] 42#0: *102 connect() failed (111: Connection refused) while connecting to upstream
    2026/06/14 03:12:00 [crit] 42#0: *200 SSL_do_handshake() failed — certificate verify failed
    2026/06/14 04:00:00 [info] 42#0: *999 worker connections: 124/1024
""")

SAMPLE_SYSLOG = textwrap.dedent("""\
    Jun 14 03:11:00 prod-worker-01 kernel: Out of memory: Kill process 4521 (java) score 891
    Jun 14 03:12:00 prod-db-01 postgres[1234]: ERROR: connection pool exhausted after 30s
    Jun 14 04:00:00 prod-api-01 nginx[42]: info: worker connections normal
""")


def _lines_from_string(text: str) -> list[str]:
    return text.strip().splitlines(keepends=True)


class TestAutoDetect:
    def test_detects_apache(self):
        assert detect_log_type(_lines_from_string(SAMPLE_APACHE)) == LogType.APACHE

    def test_detects_python(self):
        assert detect_log_type(_lines_from_string(SAMPLE_PYTHON)) == LogType.PYTHON

    def test_detects_jsonl(self):
        assert detect_log_type(_lines_from_string(SAMPLE_JSONL)) == LogType.JSONL

    def test_detects_nginx(self):
        assert detect_log_type(_lines_from_string(SAMPLE_NGINX)) == LogType.NGINX

    def test_detects_syslog(self):
        assert detect_log_type(_lines_from_string(SAMPLE_SYSLOG)) == LogType.SYSLOG


class TestApacheParser:
    def _parse(self, text: str) -> list[LogEntry]:
        tmp = Path("/tmp/test_apache.log")
        tmp.write_text(text, encoding="utf-8")
        return list(parse_file(tmp, LogType.APACHE))

    def test_parses_200_as_info(self):
        entries = self._parse(SAMPLE_APACHE)
        assert entries[0].level == "INFO"
        assert entries[0].host == "192.168.1.10"

    def test_parses_500_as_error(self):
        entries = self._parse(SAMPLE_APACHE)
        assert entries[1].level == "ERROR"

    def test_parses_401_as_warning(self):
        entries = self._parse(SAMPLE_APACHE)
        assert entries[2].level == "WARNING"

    def test_timestamp_parsed(self):
        entries = self._parse(SAMPLE_APACHE)
        ts = entries[0].timestamp
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 6
        assert ts.day == 14

    def test_log_type_set(self):
        entries = self._parse(SAMPLE_APACHE)
        assert all(e.log_type == LogType.APACHE for e in entries)


class TestPythonParser:
    def _parse(self, text: str) -> list[LogEntry]:
        tmp = Path("/tmp/test_python.log")
        tmp.write_text(text, encoding="utf-8")
        return list(parse_file(tmp, LogType.PYTHON))

    def test_parses_error(self):
        entries = self._parse(SAMPLE_PYTHON)
        assert entries[0].level == "ERROR"

    def test_parses_critical(self):
        entries = self._parse(SAMPLE_PYTHON)
        assert entries[2].level == "CRITICAL"

    def test_message_content(self):
        entries = self._parse(SAMPLE_PYTHON)
        assert "connection pool exhausted" in entries[0].message


class TestJSONLParser:
    def _parse(self, text: str) -> list[LogEntry]:
        tmp = Path("/tmp/test_jsonl.log")
        tmp.write_text(text, encoding="utf-8")
        return list(parse_file(tmp, LogType.JSONL))

    def test_parses_all_entries(self):
        entries = self._parse(SAMPLE_JSONL)
        assert len(entries) == 3

    def test_level_normalised(self):
        entries = self._parse(SAMPLE_JSONL)
        assert entries[0].level == "ERROR"
        assert entries[1].level == "CRITICAL"

    def test_host_parsed(self):
        entries = self._parse(SAMPLE_JSONL)
        assert entries[0].host == "prod-db-01"

    def test_extra_fields_preserved(self):
        entries = self._parse(SAMPLE_JSONL)
        assert "service" in entries[0].extra


class TestNGINXParser:
    def _parse(self, text: str) -> list[LogEntry]:
        tmp = Path("/tmp/test_nginx.log")
        tmp.write_text(text, encoding="utf-8")
        return list(parse_file(tmp, LogType.NGINX))

    def test_error_level(self):
        entries = self._parse(SAMPLE_NGINX)
        assert entries[0].level == "ERROR"

    def test_crit_maps_to_critical(self):
        entries = self._parse(SAMPLE_NGINX)
        assert entries[1].level == "CRITICAL"

    def test_info_level(self):
        entries = self._parse(SAMPLE_NGINX)
        assert entries[2].level == "INFO"


class TestSyslogParser:
    def _parse(self, text: str) -> list[LogEntry]:
        tmp = Path("/tmp/test_syslog.log")
        tmp.write_text(text, encoding="utf-8")
        return list(parse_file(tmp, LogType.SYSLOG))

    def test_host_parsed(self):
        entries = self._parse(SAMPLE_SYSLOG)
        assert entries[0].host == "prod-worker-01"

    def test_parses_three_entries(self):
        entries = self._parse(SAMPLE_SYSLOG)
        assert len(entries) == 3
