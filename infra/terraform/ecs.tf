module "ecs" {
  source = "./modules/ecs"

  app_name  = local.app_name
  app_image = var.app_image
  cpu       = var.app_cpu
  memory    = var.app_memory
  desired_count = var.app_desired_count

  vpc_id   = var.vpc_id != "" ? var.vpc_id : module.vpc[0].vpc_id
  subnet_ids = var.vpc_id != "" ? var.private_subnet_ids : module.vpc[0].private_subnet_ids
  target_group_arn = module.alb.target_group_arn
  alb_security_group_id = module.alb.security_group_id
  aws_region = var.aws_region

  container_environment = [
    {
      name  = "DATABASE_URL"
      value = "postgresql://${var.db_username}:${var.db_password}@${module.rds.db_endpoint}/renewaldesk"
    },
    {
      name  = "ENVIRONMENT"
      value = var.environment
    }
  ]

  tags = local.tags
}

module "alb" {
  source = "./modules/alb"

  app_name    = local.app_name
  vpc_id      = var.vpc_id != "" ? var.vpc_id : module.vpc[0].vpc_id
  subnet_ids  = var.vpc_id != "" ? var.public_subnet_ids : module.vpc[0].public_subnet_ids
  tags        = local.tags
}
