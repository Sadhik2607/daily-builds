output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace resource ID"
  value       = azurerm_log_analytics_workspace.law.id
}

output "log_analytics_workspace_key" {
  description = "Log Analytics Workspace primary shared key"
  value       = azurerm_log_analytics_workspace.law.primary_shared_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Application Insights connection string"
  value       = azurerm_application_insights.ai.connection_string
  sensitive   = true
}

output "action_group_id" {
  description = "Monitor Action Group ID"
  value       = azurerm_monitor_action_group.critical_alerts.id
}

output "workspace_portal_url" {
  description = "Azure Portal URL for the Log Analytics Workspace"
  value       = "https://portal.azure.com/#resource${azurerm_log_analytics_workspace.law.id}/overview"
}
