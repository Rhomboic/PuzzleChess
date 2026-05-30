terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3 with native lockfile locking (no DynamoDB).
  # The bucket itself is defined in state.tf and created before this backend
  # is initialized. State migrated from local with: terraform init -migrate-state
  backend "s3" {
    bucket       = "puzzlechess-tfstate-673981388599"
    key          = "puzzlechess/terraform.tfstate"
    region       = "us-west-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
