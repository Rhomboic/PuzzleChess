# ──────────────────────────────────────────────────────────────────────────────
# GitHub Actions role for the Terraform CI workflow (plan on PR, apply on merge).
#
# Reuses the GitHub OIDC provider defined in github_oidc.tf.
# Trust is scoped to two subjects only:
#   - PR events            (terraform plan)
#   - pushes to main       (terraform apply)
# Fork PRs get a different `sub` and cannot assume this role.
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "github_actions_terraform" {
  name = "${var.project}-github-actions-terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:Rhomboic/PuzzleChess:ref:refs/heads/main",
            "repo:Rhomboic/PuzzleChess:pull_request",
          ]
        }
      }
    }]
  })
}

# Permissions covering every service this Terraform config manages.
# Broad by necessity (it provisions IAM, ACM, CloudFront, Route53, etc.) —
# acceptable for a single-owner personal project. Scope down for shared/prod use.
resource "aws_iam_role_policy" "github_actions_terraform" {
  name = "${var.project}-github-actions-terraform-policy"
  role = aws_iam_role.github_actions_terraform.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageProjectServices"
        Effect = "Allow"
        Action = [
          "s3:*",
          "ecr:*",
          "ecs:*",
          "iam:*",
          "acm:*",
          "cloudfront:*",
          "route53:*",
          "secretsmanager:*",
          "logs:*",
          "sts:GetCallerIdentity",
        ]
        Resource = "*"
      },
      {
        Sid    = "ManageNetworking"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroup*",
          "ec2:RevokeSecurityGroup*",
          "ec2:CreateTags",
          "ec2:DeleteTags",
        ]
        Resource = "*"
      },
    ]
  })
}

output "github_actions_terraform_role_arn" {
  description = "Add this as AWS_TF_ROLE_ARN in GitHub repo variables"
  value       = aws_iam_role.github_actions_terraform.arn
}
