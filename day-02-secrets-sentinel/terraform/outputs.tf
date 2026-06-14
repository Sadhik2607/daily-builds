output "resource_group_name" {
  description = "Resource group containing all SecretSentinel resources."
  value       = azurerm_resource_group.main.name
}

output "acr_login_server" {
  description = "ACR login server — push your Docker image here."
  value       = azurerm_container_registry.acr.login_server
}

output "acr_push_command" {
  description = "Command to build and push the SecretSentinel image to ACR."
  value       = "docker build -t ${azurerm_container_registry.acr.login_server}/secretsentinel:latest . && docker push ${azurerm_container_registry.acr.login_server}/secretsentinel:latest"
}

output "storage_account_name" {
  description = "Storage account holding SARIF and HTML scan reports."
  value       = azurerm_storage_account.reports.name
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for querying scan logs."
  value       = azurerm_log_analytics_workspace.law.workspace_id
}

output "key_vault_uri" {
  description = "Key Vault URI storing ACR credentials and GitHub PAT."
  value       = azurerm_key_vault.kv.vault_uri
}

output "container_group_name" {
  description = "ACI container group name — start a scan with az container start."
  value       = azurerm_container_group.scanner.name
}

output "trigger_scan_command" {
  description = "Azure CLI command to trigger a scan run."
  value       = "az container start --name ${azurerm_container_group.scanner.name} --resource-group ${azurerm_resource_group.main.name}"
}
