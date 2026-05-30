output "ecr_repository_url" {
  description = "ECR repository URL — use this to tag and push images"
  value       = aws_ecr_repository.puzzlechess.repository_url
}

output "s3_bucket" {
  description = "S3 bucket where results are written"
  value       = aws_s3_bucket.results.bucket
}

output "ecs_cluster" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.puzzlechess.name
}

output "security_group_id" {
  description = "Security group ID for Fargate tasks"
  value       = aws_security_group.fargate.id
}

output "subnet_ids" {
  description = "Subnet IDs for Fargate tasks"
  value       = data.aws_subnets.default.ids
}
