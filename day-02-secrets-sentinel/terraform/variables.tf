variable "location" {
  description = "Azure region to deploy into."
  type        = string
  default     = "Canada Central"
}

variable "environment" {
  description = "Deployment environment tag (dev / staging / prod)."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "project" {
  description = "Project short-name used in resource naming."
  type        = string
  default     = "secretsentinel"
}

variable "container_image" {
  description = "Full Docker image reference to run in ACI (e.g. ghcr.io/Sadhik2607/secretsentinel:1.0.0)."
  type        = string
  default     = "ghcr.io/sadhik2607/secretsentinel:latest"
}

variable "scan_target_repo_url" {
  description = "Git repo URL to clone and scan on each scheduled run."
  type        = string
  default     = ""
}

variable "github_token" {
  description = "GitHub PAT for cloning private repos. Stored in Key Vault."
  type        = string
  sensitive   = true
  default     = ""
}

variable "acr_sku" {
  description = "Azure Container Registry SKU."
  type        = string
  default     = "Basic"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.acr_sku)
    error_message = "acr_sku must be Basic, Standard, or Premium."
  }
}

variable "aci_cpu" {
  description = "vCPU count for the Azure Container Instance."
  type        = number
  default     = 0.5
}

variable "aci_memory_gb" {
  description = "Memory (GB) for the Azure Container Instance."
  type        = number
  default     = 0.5
}

variable "notification_email" {
  description = "Email address for scan completion alerts via Azure Monitor."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
