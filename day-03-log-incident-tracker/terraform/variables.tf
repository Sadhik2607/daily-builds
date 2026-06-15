variable "resource_group" {
  description = "Azure resource group name"
  type        = string
  default     = "rg-logsentinel-dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "canadacentral"
}

variable "prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "logsentinel"
}

variable "retention_days" {
  description = "Log Analytics Workspace retention in days"
  type        = number
  default     = 30
}

variable "alert_email_addresses" {
  description = "Email addresses to notify on alerts"
  type        = list(string)
  default     = []
}

variable "alert_webhook_url" {
  description = "Webhook URL for alert notifications (e.g. Slack incoming webhook)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "critical_threshold" {
  description = "Number of CRITICAL events in 5m window before firing an alert"
  type        = number
  default     = 5
}

variable "error_threshold" {
  description = "Number of ERROR events in 10m window before firing an alert"
  type        = number
  default     = 20
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    project     = "logsentinel"
    environment = "dev"
    managed_by  = "terraform"
    daily_build = "day-03"
  }
}
