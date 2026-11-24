module "s3" {
  source = "./modules/s3"

  app_name    = local.app_name
  environment = var.environment
  tags        = local.tags
}
