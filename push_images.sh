#!/bin/bash
# Builds, tags, and pushes all 6 model images to ECR.
# Run after: terraform apply

set -e

REGION=$(terraform -chdir=terraform output -raw ecr_repository_url | cut -d'.' -f4)
ECR_URL=$(terraform -chdir=terraform output -raw ecr_repository_url)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

MODELS=(
  "claude-haiku-4-5"
  "claude-sonnet-4-6"
  "claude-opus-4-7"
  "gpt-4.1-mini"
  "gpt-4.1"
  "o3"
)

echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

echo ""
for MODEL in "${MODELS[@]}"; do
  LOCAL_IMAGE="puzzlechess-${MODEL}"
  ECR_TAG="${ECR_URL}:${MODEL}"

  echo "Building $LOCAL_IMAGE for linux/amd64..."
  docker build --platform linux/amd64 -t $LOCAL_IMAGE --build-arg MODEL=$MODEL .

  echo "Tagging as $ECR_TAG..."
  docker tag $LOCAL_IMAGE $ECR_TAG

  echo "Pushing $ECR_TAG..."
  docker push $ECR_TAG
  echo "Done: $MODEL"
  echo ""
done

echo "All images pushed to ECR."
