from datetime import datetime, timezone

from pbi_pulse.monitor import evaluate_dataset


NOW = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)


def test_failed_refresh_is_critical():
    dataset = {"id": "ds-1", "name": "Test Dataset"}
    refreshes = [
        {"status": "Failed", "startTime": "2026-06-26T06:00:00Z",
         "endTime": "2026-06-26T06:04:00Z", "serviceExceptionJson": "boom"}
    ]
    report = evaluate_dataset("WS", dataset, refreshes, now=NOW, max_age_hours=26, max_duration_min=60)
    assert report.status == "CRITICAL"
    # Latest refresh failed AND there's no successful refresh in history at all —
    # both rules legitimately fire (2 x CRITICAL = 100 - 40 - 40 = 20).
    assert report.health_score == 20
    assert any(i.rule == "refresh_failed" for i in report.issues)
    assert any(i.rule == "no_successful_refresh" for i in report.issues)


def test_failed_refresh_with_prior_success_only_flags_once():
    dataset = {"id": "ds-1b", "name": "Test Dataset 2"}
    refreshes = [
        {"status": "Failed", "startTime": "2026-06-26T06:00:00Z",
         "endTime": "2026-06-26T06:04:00Z", "serviceExceptionJson": "boom"},
        {"status": "Completed", "startTime": "2026-06-25T06:00:00Z",
         "endTime": "2026-06-25T06:18:00Z"},
    ]
    report = evaluate_dataset("WS", dataset, refreshes, now=NOW, max_age_hours=26, max_duration_min=60)
    assert report.status == "CRITICAL"
    # refresh_failed (CRITICAL, -40) + the prior success is also >26h old so
    # refresh_stale fires too (WARNING, -15) => 100 - 40 - 15 = 45.
    assert report.health_score == 45
    assert [i.rule for i in report.issues] == ["refresh_failed", "refresh_stale"]


def test_stale_refresh_is_warning():
    dataset = {"id": "ds-2", "name": "Stale Dataset"}
    refreshes = [
        {"status": "Completed", "startTime": "2026-06-24T01:00:00Z", "endTime": "2026-06-24T01:30:00Z"}
    ]
    report = evaluate_dataset("WS", dataset, refreshes, now=NOW, max_age_hours=26, max_duration_min=60)
    assert report.status == "WARNING"
    assert any(i.rule == "refresh_stale" for i in report.issues)


def test_healthy_dataset_scores_100():
    dataset = {"id": "ds-3", "name": "Healthy Dataset"}
    refreshes = [
        {"status": "Completed", "startTime": "2026-06-26T05:00:00Z", "endTime": "2026-06-26T05:06:00Z"}
    ]
    report = evaluate_dataset("WS", dataset, refreshes, now=NOW, max_age_hours=26, max_duration_min=60)
    assert report.status == "OK"
    assert report.health_score == 100


def test_no_history_is_info_only():
    dataset = {"id": "ds-4", "name": "New Dataset"}
    report = evaluate_dataset("WS", dataset, [], now=NOW, max_age_hours=26, max_duration_min=60)
    assert report.issues[0].rule == "no_refresh_history"
    assert report.health_score == 95
