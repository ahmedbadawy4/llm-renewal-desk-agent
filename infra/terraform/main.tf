terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }

  # Partial configuration: the bucket, key and region of the state are passed
  # at init time (see backend.hcl.example and the README), so no account
  # specific names live in the code.
  backend "s3" {}
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
