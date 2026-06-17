import pytest

from cloudenv.cost_report import CostResult, check_threshold, get_aws_cost, get_azure_cost


def test_check_threshold_under_budget():
    result = check_threshold("aws", "dev", amount_usd=10.0, threshold_usd=25.0)
    assert isinstance(result, CostResult)
    assert result.over_threshold is False
    assert result.percent_of_threshold == 40.0


def test_check_threshold_over_budget():
    result = check_threshold("azure", "qa", amount_usd=30.0, threshold_usd=25.0)
    assert result.over_threshold is True
    assert "OVER THRESHOLD" in result.to_alert_message()


def test_check_threshold_exactly_at_budget_counts_as_breach():
    result = check_threshold("aws", "dev", amount_usd=25.0, threshold_usd=25.0)
    assert result.over_threshold is True


def test_alert_message_includes_cloud_and_environment():
    result = check_threshold("aws", "dev", amount_usd=5.0, threshold_usd=25.0)
    msg = result.to_alert_message()
    assert "AWS" in msg
    assert "dev" in msg


def test_percent_of_threshold_handles_zero_threshold():
    result = check_threshold("aws", "dev", amount_usd=5.0, threshold_usd=0)
    assert result.percent_of_threshold == 0.0


class _FakeCostExplorerClient:
    def __init__(self, daily_amounts):
        self._daily_amounts = daily_amounts

    def get_cost_and_usage(self, **kwargs):
        return {
            "ResultsByTime": [
                {"Total": {"UnblendedCost": {"Amount": str(amt)}}} for amt in self._daily_amounts
            ]
        }


def test_get_aws_cost_sums_daily_results():
    client = _FakeCostExplorerClient([1.50, 2.25, 0.75])
    total = get_aws_cost(client, environment="dev", owner="jsmith", days_back=3)
    assert total == 4.5


class _FakeAzureRow(list):
    pass


class _FakeQueryResult:
    def __init__(self, rows):
        self.rows = rows


class _FakeCostMgmtClient:
    class query:
        @staticmethod
        def usage(scope, params):
            return _FakeQueryResult(rows=[[3.0], [4.5]])


def test_get_azure_cost_sums_daily_rows():
    total = get_azure_cost(_FakeCostMgmtClient(), scope="/subscriptions/sub/resourceGroups/rg-dev-jsmith")
    assert total == 7.5
