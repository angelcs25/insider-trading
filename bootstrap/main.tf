#Creates s3 bucket that stores terraform state for the main stack (infra/)
#Creates github OIDC identity provider + IAM role, so Github actions can deploy without storing long-lived AWS access keys anywhere

terraform {
    required-version = ">=1.10"
    required-providers = {
        aws = { source = "hashicorp/aws", version = "~> 6.0}
    }
}

provider "aws" {
    region = var.region
}

variable "region" {
    type = string
    default = "us-east-1"
}

variable "project" {
    type = string
    default = "insider-trading"
}

variable "github_repo" {
    description = "owner/name of your GitHub repo, e.g. jdoe/insider-trading"
    type = string
}

data "aws_caller_identity" "current" {}

locals {
    account_id = data.aws_caller_identity.current.account_id
}

resource "aws_s3_bucket" "tf_state" {
    bucket = "${var.project}-tf_state-${local.account.identity}"
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration { status = "Enabled" } # lets you recover a corrupted state file
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------- GitHub Actions -> AWS via OIDC ----------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only workflows in YOUR repo can assume this role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${var.project}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

# Scoped to this project's resource names, not account-wide admin.
data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "TerraformState"
    actions   = ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [aws_s3_bucket.tf_state.arn, "${aws_s3_bucket.tf_state.arn}/*"]
  }
  statement {
    sid     = "ProjectBuckets"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.project}-raw-${local.account_id}",
      "arn:aws:s3:::${var.project}-raw-${local.account_id}/*",
    ]
  }
  statement {
    sid       = "ProjectLambda"
    actions   = ["lambda:*"]
    resources = ["arn:aws:lambda:${var.region}:${local.account_id}:function:${var.project}-*"]
  }
  statement {
    sid       = "ProjectSchedule"
    actions   = ["events:*"]
    resources = ["arn:aws:events:${var.region}:${local.account_id}:rule/${var.project}-*"]
  }
  statement {
    sid     = "ProjectLogs"
    actions = ["logs:*"]
    resources = [
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${var.project}-*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${var.project}-*:*",
    ]
  }
  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }
  statement {
    sid       = "ProjectRoles"
    actions   = ["iam:*Role*", "iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

output "state_bucket" {
  value = aws_s3_bucket.tf_state.bucket
}

output "github_role_arn" {
  description = "Save this as the AWS_ROLE_ARN secret in your GitHub repo"
  value       = aws_iam_role.github_deploy.arn
}
