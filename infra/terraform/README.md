# Terraform for AWS

Terraform for running Renewal Desk on AWS: a VPC, an Application Load Balancer, an ECS Fargate service, an RDS PostgreSQL instance and an S3 bucket.

This is a reference setup. [Limits](#limits) lists what a production rollout would still need.

## What it creates

| File or module | Resources |
| --- | --- |
| `vpc.tf` | A VPC from the `terraform-aws-modules/vpc/aws` registry module (two private and two public subnets, NAT gateways for the private subnets), or your own VPC when `vpc_id` is set |
| `modules/alb` | Application Load Balancer, HTTP listener on port 80, target group with the `/health` check, security group |
| `modules/ecs` | ECS cluster `renewal-desk-cluster`, Fargate task definition and service `renewal-desk`, task and execution roles, CloudWatch log group, security group |
| `modules/rds` | PostgreSQL 15 instance with encrypted gp3 storage, 7 days of backups, subnet group and security group. Multi-AZ and deletion protection only when `environment = "production"` |
| `modules/s3` | Versioned, encrypted bucket with public access blocked |

The cluster, service and task family names match the ones in [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml).

## Prerequisites

- Terraform 1.5 or later
- AWS credentials with rights to create the resources above
- An S3 bucket for the Terraform state (the backend is configured at init time)
- An ECR repository with the application image

## Usage

```bash
cd infra/terraform

# 1. State backend: copy the example and fill in your bucket
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl

# 2. Variables: copy the example and edit it
cp terraform.tfvars.example terraform.tfvars

# 3. The database password comes from the environment, not from a file
export TF_VAR_db_password='<choose-a-password>'

terraform plan
terraform apply
```

To check the code without a backend or credentials:

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

## Variables

| Variable | Default | Description |
| --- | --- | --- |
| `aws_region` | `us-east-1` | Region |
| `environment` | `dev` | `dev`, `staging` or `production`. Only `production` enables Multi-AZ and deletion protection |
| `app_image` | `renewal-desk:latest` | Image reference for the first task definition. Set it to the ECR image |
| `app_cpu`, `app_memory` | `512`, `1024` | Fargate task size |
| `app_desired_count` | `2` | Number of tasks |
| `db_instance_class` | `db.t3.medium` | RDS instance class |
| `db_allocated_storage`, `db_max_allocated_storage` | `100`, `200` | Storage in GB, with autoscaling up to the maximum |
| `db_username` | `postgres` | Database master user |
| `db_password` | none | Database master password. Required. Use `TF_VAR_db_password` |
| `vpc_id` | empty | Use an existing VPC instead of creating one |
| `private_subnet_ids`, `public_subnet_ids` | empty | Subnets of the existing VPC |
| `db_allowed_cidr_blocks` | empty | CIDR blocks allowed to reach the database in an existing VPC |

## Outputs

`rds_endpoint`, `s3_bucket_name`, `ecs_cluster_name`, `ecs_service_name`, `alb_dns_name`, and the VPC and subnet ids.

## Deployment workflow

[`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) is a manual workflow (`workflow_dispatch`). It builds the image, pushes it to ECR, registers a new task definition revision with the new image, updates the service and runs `scripts/migrate.py` in a running task with `aws ecs execute-command`. The service has `enable_execute_command` set for this, and Terraform ignores later changes of the task definition so that `terraform apply` does not undo a deployment.

It runs in the GitHub environment `production`, where required reviewers can be set, and gets AWS credentials through OpenID Connect (OIDC). No access keys are stored in GitHub. The region is `us-east-1`, set in the `env` block of the workflow.

What you need to set up first, in the AWS account that runs the stack:

1. An IAM OIDC identity provider for GitHub (`token.actions.githubusercontent.com`, audience `sts.amazonaws.com`).
2. An IAM role whose trust policy allows only this repository and the `production` environment. The `sub` condition is `repo:<owner>/<repository>:environment:production`.
3. Permissions on that role for what the workflow calls: `ecr:GetAuthorizationToken`, the ECR push actions on the `renewal-desk` repository, `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`, `ecs:UpdateService`, `ecs:DescribeServices`, `ecs:ListTasks`, `ecs:DescribeTasks` and `ecs:ExecuteCommand`, and `iam:PassRole` for the task role and the execution role of the service.
4. In the `production` environment of the repository, a variable `AWS_ROLE_ARN` with the ARN of that role. The first step of the workflow stops with a clear message when it is missing.

## Limits

- **The database password is an ECS environment value.** `DATABASE_URL` is passed as a plain container environment variable and the password is part of the Terraform state. The ECS module already has a `container_secrets` input for a move to AWS Secrets Manager.
- **HTTP only.** The load balancer has a listener on port 80. HTTPS needs an ACM certificate and a second listener.
- **NAT gateway cost.** The registry VPC module is called with `enable_nat_gateway = true` and its default of one NAT gateway per private subnet, which bills per hour. A development setup can set `single_nat_gateway = true` in `vpc.tf`.
- **The deploy role is not created here.** This Terraform does not create the GitHub OIDC provider or the IAM role that the deploy workflow assumes, and it does not create the ECR repository.
- **S3 is not used by the application yet.** The task role has no S3 permissions, because the application writes files to local disk.
- **Local disk in the tasks.** Uploaded files and the job queue live in the task, so they are lost when a task stops and are not shared between tasks.
