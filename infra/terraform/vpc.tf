module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  count = var.vpc_id == "" ? 1 : 0

  name = "${local.app_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false

  tags = local.tags
}

output "vpc_id" {
  value = var.vpc_id != "" ? var.vpc_id : module.vpc[0].vpc_id
}

output "vpc_cidr_block" {
  value = var.vpc_id != "" ? "" : module.vpc[0].vpc_cidr_block
}

output "private_subnet_ids" {
  value = var.vpc_id != "" ? var.private_subnet_ids : module.vpc[0].private_subnet_ids
}

output "public_subnet_ids" {
  value = var.vpc_id != "" ? var.public_subnet_ids : module.vpc[0].public_subnet_ids
}

variable "public_subnet_ids" {
  type    = list(string)
  default = []
}
