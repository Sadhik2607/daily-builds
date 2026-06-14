# ──────────────────────────────────────────────────────────────────────────────
# SecretSentinel — Azure Infrastructure
# Deploys:
#   • Resource Group
#   • Azure Container Registry (push Docker image here)
#   • Azure Key Vault (GitHub PAT, ACR credentials)
#   • Log Analytics Workspace (scan run logs)
#   • Azure Container Instance (runs the scan on-demand or via Logic App trigger)
#   • Storage Account + Blob Container (SARIF / HTML report storage)
#   • Azure Monitor Alert + Action Group (email on CRITICAL findings)
# ──────────────────────────────────────────────────────────────────────────────

locals {
  prefix = "${var.project}-${var.environment}"
  common_tags = merge({
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
    repo        = "github.com/Sadhik2607/daily-builds"
  }, var.tags)
}

# ── Resource Group ────────────────────────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = local.common_tags
}

# ── Azure Container Registry ──────────────────────────────────────────────────
resource "azurerm_container_registry" "acr" {
  name                = replace("acr${local.prefix}", "-", "")   # ACR names: alphanumeric only
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.acr_sku
  admin_enabled       = true    # needed for ACI pull; use Managed Identity in prod

  tags = local.common_tags
}

# ── Log Analytics Workspace ───────────────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-${local.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

# ── Storage Account (scan reports) ───────────────────────────────────────────
resource "azurerm_storage_account" "reports" {
  name                     = replace("st${local.prefix}rpts", "-", "")
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
  }

  tags = local.common_tags
}

resource "azurerm_storage_container" "sarif" {
  name                  = "sarif-reports"
  storage_account_name  = azurerm_storage_account.reports.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "html" {
  name                  = "html-reports"
  storage_account_name  = azurerm_storage_account.reports.name
  container_access_type = "private"
}

# ── Key Vault ─────────────────────────────────────────────────────────────────
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "kv" {
  name                       = "kv-${local.prefix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false   # enable in prod

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
  }

  tags = local.common_tags
}

# Store GitHub PAT in Key Vault (if provided)
resource "azurerm_key_vault_secret" "github_token" {
  count        = var.github_token != "" ? 1 : 0
  name         = "github-token"
  value        = var.github_token
  key_vault_id = azurerm_key_vault.kv.id
}

# Store ACR admin password in Key Vault
resource "azurerm_key_vault_secret" "acr_password" {
  name         = "acr-admin-password"
  value        = azurerm_container_registry.acr.admin_password
  key_vault_id = azurerm_key_vault.kv.id
}

# ── Azure Container Instance (scan runner) ────────────────────────────────────
resource "azurerm_container_group" "scanner" {
  name                = "aci-${local.prefix}-scanner"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  ip_address_type     = "None"          # no public IP needed
  os_type             = "Linux"
  restart_policy      = "Never"         # run-once semantics

  # Pull from ACR using admin credentials
  image_registry_credential {
    server   = azurerm_container_registry.acr.login_server
    username = azurerm_container_registry.acr.admin_username
    password = azurerm_container_registry.acr.admin_password
  }

  container {
    name   = "secretsentinel"
    image  = "${azurerm_container_registry.acr.login_server}/${var.container_image}"
    cpu    = var.aci_cpu
    memory = var.aci_memory_gb

    # Override CMD to run scan and write SARIF to mounted storage
    commands = [
      "python", "main.py", "/scan-target",
      "--format", "sarif",
      "-o", "/reports/results.sarif",
      "--severity", "MEDIUM",
    ]

    # Mount storage for scan target and reports
    volume {
      name                 = "reports"
      mount_path           = "/reports"
      storage_account_name = azurerm_storage_account.reports.name
      storage_account_key  = azurerm_storage_account.reports.primary_access_key
      share_name           = azurerm_storage_share.reports_share.name
    }

    environment_variables = {
      PYTHONUNBUFFERED = "1"
    }
  }

  # Diagnostics → Log Analytics
  diagnostics {
    log_analytics {
      workspace_id  = azurerm_log_analytics_workspace.law.workspace_id
      workspace_key = azurerm_log_analytics_workspace.law.primary_shared_key
    }
  }

  tags = local.common_tags
}

# File share for reports (ACI volume mount)
resource "azurerm_storage_share" "reports_share" {
  name                 = "scanner-reports"
  storage_account_name = azurerm_storage_account.reports.name
  quota                = 5   # GB
}

# ── Azure Monitor Alert (CRITICAL findings) ───────────────────────────────────
resource "azurerm_monitor_action_group" "alerts" {
  count               = var.notification_email != "" ? 1 : 0
  name                = "ag-${local.prefix}-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "ssentinel"

  email_receiver {
    name          = "primary"
    email_address = var.notification_email
  }

  tags = local.common_tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "critical_findings" {
  count               = var.notification_email != "" ? 1 : 0
  name                = "alert-${local.prefix}-critical-secrets"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.law.id]
  severity             = 0    # Critical

  criteria {
    query                   = <<-QUERY
      ContainerInstanceLog_CL
      | where ContainerName_s == "secretsentinel"
      | where LogEntry_s contains "[CRITICAL]"
      | summarize CriticalCount = count() by bin(TimeGenerated, 5m)
      | where CriticalCount > 0
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"
  }

  action {
    action_groups = [azurerm_monitor_action_group.alerts[0].id]
  }

  tags = local.common_tags
}
