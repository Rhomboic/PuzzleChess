resource "aws_cloudfront_distribution" "dashboard" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = ["chess.adamissah.com"]
  price_class         = "PriceClass_100"  # US/Europe only — cheapest

  origin {
    domain_name = aws_s3_bucket_website_configuration.dashboard.website_endpoint
    origin_id   = "dashboard-s3"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"  # S3 website endpoint is HTTP
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "dashboard-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 300   # 5 min cache — dashboard updates when new results arrive
    max_ttl     = 3600
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.chess.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# Route 53 A record pointing chess.adamissah.com → CloudFront
resource "aws_route53_record" "chess" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "chess.adamissah.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.dashboard.domain_name
    zone_id                = aws_cloudfront_distribution.dashboard.hosted_zone_id
    evaluate_target_health = false
  }
}

output "cloudfront_url" {
  description = "CloudFront distribution URL (before DNS propagates)"
  value       = "https://${aws_cloudfront_distribution.dashboard.domain_name}"
}

output "dashboard_url" {
  description = "Dashboard URL"
  value       = "https://chess.adamissah.com"
}
