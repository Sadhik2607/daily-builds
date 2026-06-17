"""Cost threshold checks backed by AWS Cost Explorer and Azure Cost
Management. Both `get_*_cost` functions accept an injected client so they're
unit-testable without real cloud credentials; the CLI wires up boto3 / the
Azure SDK at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CostResult:
    cloud: str
    environment: str
    amount_usd: float
    threshold_usd: float

    @property
    def over_threshold(self) -> bool:
        return self.amount_usd >= self.threshold_usd

    @property
    def percent_of_threshold(self) -> float:
        if self.threshold_usd == 0:
            return 0.0
        return round((self.amount_usd / self.threshold_usd) * 100, 1)

    def to_alert_message(self) -> str:
        status = "OVER THRESHOLD" if self.over_threshold else "within budget"
        return (
            f"[{self.cloud.upper()}] environment={self.environment} "
            f"cost=${self.amount_usd:.2f} threshold=${self.threshold_usd:.2f} "
            f"({self.percent_of_threshold}% of budget) — {status}"
        )


def get_aws_cost(ce_client, environment: str, owner: str, days_back: int = 7) -> float:
    """Query AWS Cost Explorer, filtered to resources tagged with this
    environment, summed over the trailing `days_back` days.
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    response = ce_client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        Filter={
            "And": [
                {"Tags": {"Key": "Environment", "Values": [environment]}},
                {"Tags": {"Key": "Owner", "Values": [owner]}},
            ]
        },
    )
    total = 0.0
    for result in response.get("ResultsByTime", []):
        total += float(result["Total"]["UnblendedCost"]["Amount"])
    return round(total, 2)


def get_azure_cost(cost_mgmt_client, scope: str, days_back: int = 7) -> float:
    """Query Azure Cost Management's usage details API for a resource-group
    scope (one per environment), summed over the trailing `days_back` days.
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    result = cost_mgmt_client.query.usage(
        scope,
        {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            },
        },
    )
    rows = getattr(result, "rows", None) or result.get("rows", [])
    return round(sum(float(row[0]) for row in rows), 2)


def check_threshold(cloud: str, environment: str, amount_usd: float, threshold_usd: float) -> CostResult:
    """Pure function wrapping the comparison so it's trivially unit-testable
    independent of either cloud SDK.
    """
    return CostResult(cloud=cloud, environment=environment, amount_usd=amount_usd, threshold_usd=threshold_usd)
