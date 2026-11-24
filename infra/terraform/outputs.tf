output "rds_endpoint" {
  value       = module.rds.db_endpoint
  description = "RDS PostgreSQL endpoint"
  sensitive   = false
}

output "s3_bucket_name" {
  value       = module.s3.bucket_name
  description = "S3 bucket name for object storage"
}

output "ecs_cluster_name" {
  value       = module.ecs.cluster_name
  description = "ECS cluster name"
}

output "ecs_service_name" {
  value       = module.ecs.service_name
  description = "ECS service name"
}

output "alb_dns_name" {
  value       = module.alb.alb_dns_name
  description = "ALB DNS name"
}

output "github_deploy_role_arn" {
  value       = one(aws_iam_role.github_deploy[*].arn)
  description = "Role for the deploy workflow. Set it as the variable AWS_ROLE_ARN in the GitHub environment production. Null when github_repository is empty"
}
