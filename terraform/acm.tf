# ACM cert must be in us-east-1 for CloudFront
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_acm_certificate" "chess" {
  provider          = aws.us_east_1
  domain_name       = "chess.adamissah.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation record in Route 53
resource "aws_route53_record" "chess_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.chess.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.main.zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "chess" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.chess.arn
  validation_record_fqdns = [for r in aws_route53_record.chess_cert_validation : r.fqdn]
}
