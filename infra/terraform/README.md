# Terraform (placeholder)

This directory will hold modules for provisioning AWS ECS (Fargate), RDS Postgres (with pgvector), S3 buckets, and OpenSearch. Start with:
- `providers.tf` referencing AWS + remote state
- `network.tf` for VPC/subnets
- `ecs.tf` for service/task definition w/ OTel sidecar
- `rds.tf` for Postgres 15 + parameter group enabling pgvector
- `s3.tf` for object storage bucket + lifecycle policies

Coming soon.
