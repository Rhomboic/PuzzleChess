#!/bin/bash
# run_model.sh — build, push, and launch the benchmark for a single model.
#
# Usage:  ./run_model.sh <model-name>
# Example: ./run_model.sh claude-opus-4-8
#
# The model must already be registered in agent/agent.py and have an ECS task
# definition (added via terraform var.models + merge). API keys come from
# Secrets Manager at runtime; nothing sensitive is needed here.

set -euo pipefail

MODEL="${1:-}"
if [ -z "$MODEL" ]; then
  echo "Usage: ./run_model.sh <model-name>"
  echo "Example: ./run_model.sh claude-opus-4-8"
  exit 1
fi

REGION="us-west-1"
CLUSTER="puzzlechess"
PROJECT="puzzlechess"

echo "==> Reading infra values from terraform outputs..."
ECR_URL=$(terraform -chdir=terraform output -raw ecr_repository_url)
SECURITY_GROUP=$(terraform -chdir=terraform output -raw security_group_id)
SUBNETS=$(terraform -chdir=terraform output -json subnet_ids | jq -r 'join(",")')
TASK_DEF="${PROJECT}-${MODEL//./-}"   # ECS family: dots -> dashes

echo "  ECR:       $ECR_URL"
echo "  Cluster:   $CLUSTER"
echo "  Task def:  $TASK_DEF"
echo ""

# ── 1. Build (linux/amd64 for Fargate) ────────────────────────────────────────
echo "==> Building image for $MODEL (linux/amd64)..."
docker build --platform linux/amd64 \
  -t "puzzlechess-${MODEL}" \
  --build-arg MODEL="$MODEL" .

# ── 2. Push to ECR ────────────────────────────────────────────────────────────
echo "==> Logging in to ECR and pushing..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_URL"
docker tag "puzzlechess-${MODEL}" "${ECR_URL}:${MODEL}"
docker push "${ECR_URL}:${MODEL}"

# ── 3. Launch the task on Fargate ─────────────────────────────────────────────
echo "==> Launching ECS task..."
TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --region "$REGION" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' \
  --output text)

echo ""
echo "Task launched: $TASK_ARN"
echo "Logs: CloudWatch /ecs/puzzlechess (stream prefix: $MODEL)"
echo "Results will appear in S3 and auto-update the dashboard when the run finishes."
