resource "aws_ecs_cluster" "puzzlechess" {
  name = var.project
}

resource "aws_cloudwatch_log_group" "puzzlechess" {
  name              = "/ecs/${var.project}"
  retention_in_days = 7
}

resource "aws_ecs_task_definition" "model" {
  for_each = toset(var.models)

  family                   = "${var.project}-${replace(each.key, ".", "-")}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = var.project
    image = "${aws_ecr_repository.puzzlechess.repository_url}:${each.key}"

    environment = [
      { name = "MODEL",              value = each.key },
      { name = "S3_BUCKET",          value = aws_s3_bucket.results.bucket },
      { name = "S3_KEY_PREFIX",      value = "runs/" },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    ]

    secrets = [
      {
        name      = "ANTHROPIC_API_KEY"
        valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn
      },
      {
        name      = "OPENAI_API_KEY"
        valueFrom = aws_secretsmanager_secret.openai_api_key.arn
      },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.puzzlechess.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = each.key
      }
    }
  }])
}
