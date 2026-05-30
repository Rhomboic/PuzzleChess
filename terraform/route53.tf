resource "aws_route53_zone" "main" {
  name = "adamissah.com"
}

# Pin the domain registration's nameservers to the hosted zone's delegation set.
# If the hosted zone is ever recreated (new nameservers), the next apply updates
# the registrar to match automatically — preventing the DNS/cert outage we hit
# when the registrar pointed at a destroyed zone's nameservers.
# route53domains is a us-east-1 global service, so it uses the us_east_1 provider.
resource "aws_route53domains_registered_domain" "main" {
  provider    = aws.us_east_1
  domain_name = "adamissah.com"

  dynamic "name_server" {
    for_each = aws_route53_zone.main.name_servers
    content {
      name = name_server.value
    }
  }

  # Ensure the CI role has route53domains permissions before this is managed.
  depends_on = [aws_iam_role_policy.github_actions_terraform]
}

output "nameservers" {
  description = "Route 53 nameservers — registrar is pinned to these via aws_route53domains_registered_domain"
  value       = aws_route53_zone.main.name_servers
}
