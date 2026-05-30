resource "aws_route53_zone" "main" {
  name = "adamissah.com"
}

output "nameservers" {
  description = "Route 53 nameservers — confirm these match your domain registration"
  value       = aws_route53_zone.main.name_servers
}
