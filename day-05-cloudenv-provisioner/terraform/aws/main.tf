terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  name_prefix = "${var.environment}-${var.owner}"

  common_tags = merge(var.tags, {
    Environment = var.environment
    Owner       = var.owner
    Project     = var.project
  })
}
