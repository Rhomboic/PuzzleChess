# ──────────────────────────────────────────────────────────────────────────────
# Remote state backend bucket
#
# Holds the Terraform state file. Versioned (so we can roll back a bad apply)
# and encrypted. State locking is handled by S3-native lockfiles
# (use_lockfile = true in the backend block in main.tf) — no DynamoDB needed.
#
# NOTE: this bucket is managed by the same config it backs. prevent_destroy
# guards against accidentally deleting the bucket that stores our state.
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
