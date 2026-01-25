module "rds" {
  source = "./modules/rds"

  app_name          = local.app_name
  vpc_id            = var.vpc_id != "" ? var.vpc_id : module.vpc[0].vpc_id
  subnet_ids        = var.vpc_id != "" ? var.private_subnet_ids : module.vpc[0].private_subnet_ids
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  db_username       = var.db_username
  db_password       = var.db_password
  multi_az          = var.environment == "production"
  deletion_protection = var.environment == "production"
  allowed_cidr_blocks = var.vpc_id != "" ? [] : [module.vpc[0].vpc_cidr_block]
  tags              = local.tags
}

variable "db_username" {
  type      = string
  sensitive = true
  default   = "postgres"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "private_subnet_ids" {
  type    = list(string)
  default = []
}
