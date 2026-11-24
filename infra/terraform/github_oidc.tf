# Access for the GitHub Actions deploy workflow through OpenID Connect (OIDC).
#
# .github/workflows/deploy.yml assumes the role below, so no AWS access keys are
# stored in GitHub. Nothing here is created until github_repository is set.

locals {
  github_oidc_host    = "token.actions.githubusercontent.com"
  deploy_role_enabled = var.github_repository != ""

  # The deploy job runs in the GitHub environment "production". This is the
  # name of a GitHub environment, not the Terraform variable "environment".
  github_environment = "production"
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# An AWS account can have only one provider for this URL. When the account
# already has it, set create_github_oidc_provider to false and it is looked up.
resource "aws_iam_openid_connect_provider" "github" {
  count = local.deploy_role_enabled && var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
  tags           = local.tags
}

data "aws_iam_openid_connect_provider" "github" {
  count = local.deploy_role_enabled && !var.create_github_oidc_provider ? 1 : 0

  url = "https://${local.github_oidc_host}"
}

locals {
  github_oidc_provider_arn = one(concat(
    aws_iam_openid_connect_provider.github[*].arn,
    data.aws_iam_openid_connect_provider.github[*].arn,
  ))

  arn_prefix         = "arn:${data.aws_partition.current.partition}"
  account_id         = data.aws_caller_identity.current.account_id
  ecr_repository_arn = "${local.arn_prefix}:ecr:${var.aws_region}:${local.account_id}:repository/${local.app_name}"
  ecs_cluster_arn    = "${local.arn_prefix}:ecs:${var.aws_region}:${local.account_id}:cluster/${module.ecs.cluster_name}"
  ecs_service_arn    = "${local.arn_prefix}:ecs:${var.aws_region}:${local.account_id}:service/${module.ecs.cluster_name}/${module.ecs.service_name}"
  ecs_task_arns      = "${local.arn_prefix}:ecs:${var.aws_region}:${local.account_id}:task/${module.ecs.cluster_name}/*"
}

# Only this repository, running a job in the "production" environment, can
# assume the role. Pull requests and other branches get no credentials.
data "aws_iam_policy_document" "github_deploy_trust" {
  count = local.deploy_role_enabled ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values   = ["repo:${var.github_repository}:environment:${local.github_environment}"]
    }
  }
}

# Exactly what the deploy workflow calls, and nothing else.
data "aws_iam_policy_document" "github_deploy" {
  count = local.deploy_role_enabled ? 1 : 0

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [local.ecr_repository_arn]
  }

  # These two actions do not support resource-level permissions.
  statement {
    sid = "EcsTaskDefinition"
    actions = [
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  statement {
    sid = "EcsService"
    actions = [
      "ecs:DescribeServices",
      "ecs:UpdateService",
    ]
    resources = [local.ecs_service_arn]
  }

  statement {
    sid       = "EcsListTasks"
    actions   = ["ecs:ListTasks"]
    resources = ["*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [local.ecs_cluster_arn]
    }
  }

  # Opens the session that runs scripts/migrate.py in a running task.
  statement {
    sid = "EcsExec"
    actions = [
      "ecs:DescribeTasks",
      "ecs:ExecuteCommand",
    ]
    resources = [
      local.ecs_cluster_arn,
      local.ecs_task_arns,
    ]
  }

  # A new task definition revision names the task and execution roles.
  statement {
    sid     = "PassServiceRoles"
    actions = ["iam:PassRole"]
    resources = [
      module.ecs.execution_role_arn,
      module.ecs.task_role_arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count = local.deploy_role_enabled ? 1 : 0

  name               = "${local.app_name}-github-deploy"
  description        = "Assumed by the GitHub Actions deploy workflow through OIDC"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_trust[0].json
  tags               = local.tags
}

resource "aws_iam_role_policy" "github_deploy" {
  count = local.deploy_role_enabled ? 1 : 0

  name   = "${local.app_name}-github-deploy-policy"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy[0].json
}
