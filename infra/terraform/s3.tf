module "s3" {
  source = "./modules/s3"

  app_name    = local.app_name
  environment = var.environment
  tags        = local.tags
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}
