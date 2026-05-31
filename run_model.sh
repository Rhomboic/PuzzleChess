#!/bin/bash
# run_model.sh — build, push, and launch the benchmark for a single model.
#
# Usage:  ./run_model.sh <model-name> [api-model-id] [--reasoning]
# Examples:
#   ./run_model.sh claude-opus-4-8
#   ./run_model.sh claude-opus-4-8 --reasoning
#   ./run_model.sh claude-sonnet-3-7 claude-3-7-sonnet-20250219 --reasoning
#
# The model must be registered in agent/agent.py and have an ECS task definition
# (terraform var.models). API keys come from Secrets Manager at runtime.
# --reasoning passes REASONING=true as a container env override; main.py turns on
# extended thinking and writes to a separate {model}_reasoning_results.json so it
# does not overwrite the regular run.

set -euo pipefail

# ── Parse args: positional <model> [api-id], plus optional --reasoning ─────────
MODEL=""
API_ID=""
REASONING="false"
for arg in "$@"; do
  case "$arg" in
    --reasoning) REASONING="true" ;;
    *)
      if [ -z "$MODEL" ]; then MODEL="$arg"
      elif [ -z "$API_ID" ]; then API_ID="$arg"
      fi
      ;;
  esac
done
API_ID="${API_ID:-$MODEL}"

if [ -z "$MODEL" ]; then
  echo "Usage: ./run_model.sh <model-name> [api-model-id] [--reasoning]"
  echo "Example: ./run_model.sh claude-opus-4-8"
  echo "Example: ./run_model.sh claude-opus-4-8 --reasoning"
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
echo "  Reasoning: $REASONING"
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
# REASONING is a runtime container env override (the image bakes only MODEL), so
# the same image/task-def serves both regular and reasoning runs.
echo "==> Launching ECS task (REASONING=$REASONING)..."
TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --region "$REGION" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
  --overrides "{\"containerOverrides\":[{\"name\":\"${PROJECT}\",\"environment\":[{\"name\":\"REASONING\",\"value\":\"${REASONING}\"}]}]}" \
  --query 'tasks[0].taskArn' \
  --output text)

echo ""
echo "Task launched: $TASK_ARN"
echo "Logs: CloudWatch /ecs/puzzlechess (stream prefix: $MODEL)"
echo "Results will appear in S3 and auto-update the dashboard when the run finishes."
