#!/bin/bash
# Deploys dashboard files to S3 and invalidates CloudFront cache.
# Run after: terraform apply

set -e

BUCKET=$(terraform -chdir=terraform output -raw dashboard_url | sed 's|https://||')
DASHBOARD_BUCKET=$(aws s3 ls | grep puzzlechess-dashboard | awk '{print $3}')
CF_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items[?contains(@,'chess.adamissah.com')]].Id" --output text)

echo "Deploying dashboard to s3://$DASHBOARD_BUCKET ..."
aws s3 sync dashboard/ s3://$DASHBOARD_BUCKET/ \
  --delete \
  --cache-control "max-age=300"

echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id $CF_ID \
  --paths "/*"

echo "Done. Dashboard live at https://chess.adamissah.com"
