# Secrets Manager — API keys stored here, never in code or task definitions
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name                    = "${var.project}/anthropic-api-key"
  recovery_window_in_days = 0  # allow immediate deletion if needed
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.project}/openai-api-key"
  recovery_window_in_days = 0
}
