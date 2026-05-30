#!/bin/bash
# Builds one Docker image per model, named puzzlechess-{model}.

set -e

MODELS=(
  "claude-haiku-4-5"
  "claude-sonnet-4-6"
  "claude-opus-4-7"
  "gpt-4.1-mini"
  "gpt-4.1"
  "o3"
)

for MODEL in "${MODELS[@]}"; do
  IMAGE="puzzlechess-${MODEL}"
  echo "Building image: $IMAGE ..."
  docker build -t "$IMAGE" --build-arg MODEL="$MODEL" .
  echo "Done: $IMAGE"
  echo ""
done

echo "All images built."
docker images | grep puzzlechess
