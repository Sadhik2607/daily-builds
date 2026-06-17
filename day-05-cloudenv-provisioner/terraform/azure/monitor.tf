resource "azurerm_monitor_action_group" "cost_alerts" {
  name                = "${local.name_prefix}-cost-ag"
  resource_group_name = azurerm_resource_group.env.name
  short_name          = substr("${var.environment}${var.owner}", 0, 12)
  tags                = local.common_tags

  dynamic "email_receiver" {
    for_each = var.alert_email != "" ? [var.alert_email] : []
    content {
      name                    = "cost-alert-email"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }
}

# Azure Consumption Budget scoped to this environment's resource group,
# firing at 80% (forecasted) and 100% (actual) of cost_threshold_usd —
# the Azure-side equivalent of the AWS Budgets resource in the AWS module.
resource "azurerm_consumption_budget_resource_group" "env" {
  name              = "${local.name_prefix}-budget"
  resource_group_id = azurerm_resource_group.env.id

  amount     = var.cost_threshold_usd
  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Forecasted"

    contact_groups = [azurerm_monitor_action_group.cost_alerts.id]
  }

  notification {
    enabled   = true
    threshold = 100
    operator  = "GreaterThan"

    contact_groups = [azurerm_monitor_action_group.cost_alerts.id]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
