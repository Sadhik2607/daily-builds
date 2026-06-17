terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  name_prefix = "${var.environment}-${var.owner}"

  common_tags = merge(var.tags, {
    Environment = var.environment
    Owner       = var.owner
    Project     = var.project
  })
}

resource "azurerm_resource_group" "env" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.common_tags
}
