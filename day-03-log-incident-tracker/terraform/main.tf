terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

provider "azurerm" {
  features {}
}

# ── Resource Group ────────────────────────────────────────────────────────────
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group
  location = var.location
  tags     = var.tags
}

# ── Log Analytics Workspace ──────────────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.prefix}-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days

  tags = var.tags
}

# ── Application Insights (optional APM) ─────────────────────────────────────
resource "azurerm_application_insights" "ai" {
  name                = "${var.prefix}-ai"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"

  tags = var.tags
}

# ── Action Group (email + webhook) ───────────────────────────────────────────
resource "azurerm_monitor_action_group" "critical_alerts" {
  name                = "${var.prefix}-critical-ag"
  resource_group_name = azurerm_resource_group.rg.name
  short_name          = "logsentinel"

  dynamic "email_receiver" {
    for_each = var.alert_email_addresses
    content {
      name          = "email-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }

  dynamic "webhook_receiver" {
    for_each = var.alert_webhook_url != "" ? [1] : []
    content {
      name        = "logsentinel-webhook"
      service_uri = var.alert_webhook_url
    }
  }

  tags = var.tags
}

# ── Scheduled Query Alert — CRITICAL Error Rate ──────────────────────────────
# Fires when >5 CRITICAL events occur within a 5-minute evaluation window
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "critical_error_rate" {
  name                = "${var.prefix}-critical-error-rate"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  scopes               = [azurerm_log_analytics_workspace.law.id]
  severity             = 0  # Critical

  criteria {
    query                   = <<-KQL
      // LogSentinel — CRITICAL incident rate query
      // Assumes logs are ingested via Custom Log table or through Diagnostic Settings
      union isfuzzy=true
        (AppTraces
          | where SeverityLevel >= 3
          | where Message has_any ("CRITICAL", "connection pool exhausted", "OutOfMemoryError",
                                    "CrashLoopBackOff", "SSL certificate chain broken",
                                    "brute-force", "account lockout", "no space left on device")
        ),
        (Syslog
          | where SeverityLevel == "err" or SeverityLevel == "crit" or SeverityLevel == "emerg"
          | project TimeGenerated, Message = SyslogMessage
        )
      | summarize EventCount = count() by bin(TimeGenerated, 5m)
      | where EventCount > ${var.critical_threshold}
    KQL
    time_aggregation_method = "Count"
    threshold               = var.critical_threshold
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical_alerts.id]
  }

  auto_mitigation_enabled = true
  description             = "LogSentinel: CRITICAL error rate exceeded ${var.critical_threshold} events in 5 minutes"

  tags = var.tags
}

# ── Scheduled Query Alert — High Error Rate (ERROR level) ───────────────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "high_error_rate" {
  name                = "${var.prefix}-high-error-rate"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  evaluation_frequency = "PT10M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.law.id]
  severity             = 1  # Error

  criteria {
    query                   = <<-KQL
      AppTraces
      | where SeverityLevel >= 2
      | summarize ErrorCount = count() by bin(TimeGenerated, 10m)
      | where ErrorCount > ${var.error_threshold}
    KQL
    time_aggregation_method = "Count"
    threshold               = var.error_threshold
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical_alerts.id]
  }

  auto_mitigation_enabled = true
  description             = "LogSentinel: High error rate — >20 errors in 10m window"

  tags = var.tags
}
