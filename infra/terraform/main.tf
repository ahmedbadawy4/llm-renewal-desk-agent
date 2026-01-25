terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "renewal-desk-terraform-state"
    key    = "renewal-desk/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  app_name = "renewal-desk"
  tags = {
    Environment = var.environment
    Application = local.app_name
    ManagedBy   = "Terraform"
  }
}
