# Terraform Infrastructure for Renewal Desk Agent

This directory contains Terraform modules for deploying the Renewal Desk Agent to AWS.

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured
- Appropriate AWS permissions

## Modules

- **RDS**: PostgreSQL database with pgvector extension
- **S3**: Object storage for documents
- **ECS**: Fargate service for the application
- **ALB**: Application Load Balancer
- **VPC**: Network infrastructure (optional, can use existing VPC)

## Usage

1. Initialize Terraform:
```bash
cd infra/terraform
terraform init
```

2. Create a `terraform.tfvars` file:
```hcl
aws_region = "us-east-1"
environment = "production"
db_password = "your-secure-password"
app_image = "your-ecr-repo/renewal-desk:latest"
```

3. Plan the deployment:
```bash
terraform plan
```

4. Apply the infrastructure:
```bash
terraform apply
```

## Outputs

- `rds_endpoint`: RDS PostgreSQL endpoint
- `s3_bucket_name`: S3 bucket for object storage
- `ecs_cluster_name`: ECS cluster name
- `ecs_service_name`: ECS service name

## CI/CD

The `.github/workflows/deploy.yml` file contains the GitHub Actions workflow for automated deployment.
