# GitHub OIDC provider — lets GitHub Actions authenticate to AWS without stored credentials
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# IAM role that GitHub Actions assumes
resource "aws_iam_role" "github_actions_deploy" {
  name = "${var.project}-github-actions-deploy"

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
          # Only allow workflows from your repo
          "token.actions.githubusercontent.com:sub" = "repo:Rhomboic/PuzzleChess:*"
        }
      }
    }]
  })
}

# Permissions: sync dashboard S3 + invalidate CloudFront
resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "${var.project}-github-actions-deploy-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.dashboard.arn,
          "${aws_s3_bucket.dashboard.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:ListDistributions"]
        Resource = "*"
      }
    ]
  })
}

output "github_actions_role_arn" {
  description = "Add this as AWS_ROLE_ARN in GitHub repo variables"
  value       = aws_iam_role.github_actions_deploy.arn
}
