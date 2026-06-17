output "resource_group_name" {
  value = azurerm_resource_group.env.name
}

output "vm_name" {
  value = azurerm_linux_virtual_machine.env.name
}

output "storage_account_name" {
  value = azurerm_storage_account.env.name
}

output "role_definition_id" {
  value = azurerm_role_definition.env_role.role_definition_resource_id
}

output "cost_action_group_id" {
  value = azurerm_monitor_action_group.cost_alerts.id
}
