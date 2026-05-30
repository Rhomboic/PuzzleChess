#!/bin/bash
# Triggers all 6 model ECS tasks in parallel on Fargate.
# Run after: terraform apply && ./push_images.sh
# API keys are injected from AWS Secrets Manager — no keys needed here.

set -e

CLUSTER=$(terraform -chdir=terraform output -raw ecs_cluster)
REGION=$(terraform -chdir=terraform output -raw ecr_repository_url | cut -d'.' -f4)
SECURITY_GROUP=$(terraform -chdir=terraform output -raw security_group_id)
SUBNETS=$(terraform -chdir=terraform output -json subnet_ids | jq -r 'join(",")')
PROJECT="puzzlechess"

MODELS=(
  "claude-haiku-4-5"
  "claude-sonnet-4-6"
  "claude-opus-4-7"
  "gpt-4.1-mini"
  "gpt-4.1"
  "o3"
)

echo "Launching all 6 model tasks in parallel..."
echo ""

for MODEL in "${MODELS[@]}"; do
  TASK_DEF="${PROJECT}-${MODEL//./-}"

  echo "Starting task: $TASK_DEF"
  aws ecs run-task \
    --cluster $CLUSTER \
    --task-definition $TASK_DEF \
    --launch-type FARGATE \
    --region $REGION \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
    --query 'tasks[0].taskArn' \
    --output text &
done

wait
echo ""
echo "All 6 tasks launched. Monitor in ECS console or CloudWatch."
echo "Results will appear in S3 as each container finishes."
