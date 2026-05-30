resource "aws_s3_bucket" "results" {
  bucket = "${var.project}-results-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket = aws_s3_bucket.results.id

  # ACLs stay fully blocked (we don't use ACLs). Policy-based public access is
  # allowed so the dashboard (chess.adamissah.com) can fetch results JSONs
  # directly from the browser. Only the runs/ prefix is exposed; see policy below.
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

# Public read for benchmark result files only (non-sensitive data).
# Lets the dashboard fetch runs/manifest.json and runs/<model>_results.json
# anonymously from the browser. Live results stay auto-updating.
resource "aws_s3_bucket_policy" "results_public_read" {
  bucket     = aws_s3_bucket.results.id
  depends_on = [aws_s3_bucket_public_access_block.results]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadResults"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.results.arn}/runs/*"
    }]
  })
}

resource "aws_s3_bucket_cors_configuration" "results" {
  bucket = aws_s3_bucket.results.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}
