module "rds" {
  source = "./modules/rds"

  app_name              = local.app_name
  vpc_id                = var.vpc_id != "" ? var.vpc_id : module.vpc[0].vpc_id
  subnet_ids            = var.vpc_id != "" ? var.private_subnet_ids : module.vpc[0].private_subnet_ids
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  db_username           = var.db_username
  db_password           = var.db_password
  multi_az              = var.environment == "production"
  deletion_protection   = var.environment == "production"
  allowed_cidr_blocks   = var.vpc_id != "" ? var.db_allowed_cidr_blocks : [module.vpc[0].vpc_cidr_block]
  tags                  = local.tags
}

variable "db_username" {
  description = "Master user of the database"
  type        = string
  sensitive   = true
  default     = "postgres"
}

variable "db_password" {
  description = "Master password of the database. Pass it with TF_VAR_db_password, not in a file"
  type        = string
  sensitive   = true
}

variable "private_subnet_ids" {
  description = "Private subnets for ECS and RDS when vpc_id is set"
  type        = list(string)
  default     = []
}

variable "db_allowed_cidr_blocks" {
  description = "CIDR blocks that may reach the database on port 5432 when vpc_id is set. A new VPC gets its own CIDR automatically"
  type        = list(string)
  default     = []
}
