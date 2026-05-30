variable "aws_region" {
  description = "AWS region"
  default     = "us-west-1"
}

variable "project" {
  description = "Project name used for naming resources"
  default     = "puzzlechess"
}

variable "models" {
  description = "List of model names — one ECS task definition per model"
  type        = list(string)
  default = [
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o3",
  ]
}
