"""Health-rule engine: turns raw workspace/dataset/refresh data into issues."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dtparser

SEVERITY_WEIGHT = {"CRITICAL": 40, "WARNING": 15, "INFO": 5}


@dataclass
class Issue:
    rule: str
    severity: str
    detail: str


@dataclass
class DatasetReport:
    workspace: str
    dataset: str
    dataset_id: str
    last_refresh_end: str | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def health_score(self) -> int:
        score = 100
        for issue in self.issues:
            score -= SEVERITY_WEIGHT.get(issue.severity, 0)
        return max(score, 0)

    @property
    def status(self) -> str:
        if any(i.severity == "CRITICAL" for i in self.issues):
            return "CRITICAL"
        if any(i.severity == "WARNING" for i in self.issues):
            return "WARNING"
        return "OK"


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return dtparser.isoparse(ts)


def evaluate_dataset(
    workspace_name: str,
    dataset: dict[str, Any],
    refreshes: list[dict[str, Any]],
    *,
    now: datetime,
    max_age_hours: int,
    max_duration_min: int,
) -> DatasetReport:
    report = DatasetReport(
        workspace=workspace_name,
        dataset=dataset["name"],
        dataset_id=dataset["id"],
        last_refresh_end=None,
    )

    if not refreshes:
        report.issues.append(
            Issue("no_refresh_history", "INFO", "No refresh history available")
        )
        return report

    latest = refreshes[0]
    report.last_refresh_end = latest.get("endTime")

    if latest.get("status") == "Failed":
        error = latest.get("serviceExceptionJson") or latest.get("error") or "unknown error"
        report.issues.append(Issue("refresh_failed", "CRITICAL", f"Refresh failed: {error}"))

    last_success = next((r for r in refreshes if r.get("status") == "Completed"), None)
    if last_success and last_success.get("endTime"):
        end = _parse(last_success["endTime"])
        age_hours = (now - end).total_seconds() / 3600
        if age_hours > max_age_hours:
            report.issues.append(
                Issue(
                    "refresh_stale",
                    "WARNING",
                    f"Last success {age_hours:.1f}h ago (threshold {max_age_hours}h)",
                )
            )

        start = _parse(last_success.get("startTime"))
        if start:
            duration_min = (end - start).total_seconds() / 60
            if duration_min > max_duration_min:
                report.issues.append(
                    Issue(
                        "long_running_refresh",
                        "WARNING",
                        f"Last refresh took {duration_min:.0f}m (threshold {max_duration_min}m)",
                    )
                )
    elif not last_success:
        report.issues.append(
            Issue("no_successful_refresh", "CRITICAL", "No successful refresh in recorded history")
        )

    return report


def scan(
    client,
    *,
    workspace_filter: list[str] | None = None,
    max_age_hours: int = 26,
    max_duration_min: int = 60,
    now: datetime | None = None,
) -> list[DatasetReport]:
    now = now or datetime.now(timezone.utc)
    reports: list[DatasetReport] = []

    for ws in client.list_workspaces():
        if workspace_filter and ws["name"] not in workspace_filter:
            continue
        datasets = client.list_datasets(ws["id"])
        for ds in datasets:
            refreshes = client.list_refreshes(ws["id"], ds["id"])
            reports.append(
                evaluate_dataset(
                    ws["name"],
                    ds,
                    refreshes,
                    now=now,
                    max_age_hours=max_age_hours,
                    max_duration_min=max_duration_min,
                )
            )
    return reports
