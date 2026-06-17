resource "aws_sns_topic" "cost_alerts" {
  name = "${local.name_prefix}-cost-alerts"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "cost_alert_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Native AWS Budgets threshold alert — fires at 80% (forecast) and 100%
# (actual) of cost_threshold_usd, scoped to this environment's tags.
resource "aws_budgets_budget" "env_cost_threshold" {
  name              = "${local.name_prefix}-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.cost_threshold_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"

  cost_filter {
    name = "TagKeyValue"
    values = [
      format("user:Environment$%s", var.environment),
      format("user:Owner$%s", var.owner),
    ]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type              = "PERCENTAGE"
    notification_type           = "FORECASTED"
    subscriber_sns_topic_arns   = [aws_sns_topic.cost_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type              = "PERCENTAGE"
    notification_type           = "ACTUAL"
    subscriber_sns_topic_arns   = [aws_sns_topic.cost_alerts.arn]
  }
}

# CloudWatch billing alarm as a second signal, independent of AWS Budgets'
# (sometimes-delayed) evaluation cadence.
resource "aws_cloudwatch_metric_alarm" "billing_alarm" {
  alarm_name          = "${local.name_prefix}-billing-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 21600 # 6 hours
  statistic           = "Maximum"
  threshold           = var.cost_threshold_usd
  alarm_description   = format("Fires when estimated charges for %s exceed $%s.", local.name_prefix, var.cost_threshold_usd)
  alarm_actions       = [aws_sns_topic.cost_alerts.arn]

  dimensions = {
    Currency = "USD"
  }

  tags = local.common_tags
}
