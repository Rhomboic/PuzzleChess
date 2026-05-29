# PuzzleChess

An LLM agent benchmark that evaluates how well AI models solve chess puzzles. Runs as an ephemeral Docker container on AWS ECS Fargate.

## What it does

1. Loads filtered chess puzzles from a Lichess dataset (`data/`)
2. Sends each puzzle to an LLM agent (`agent/`) which outputs the best move in UCI notation
3. Scores the agent's answers against the correct solutions (`eval/`)
4. Writes results to S3 and exits

## Project structure

```
PuzzleChess/
├── data/           # Filtered puzzle CSV (not committed)
├── agent/          # LLM agent loop (Claude / OpenAI)
├── eval/           # Scoring logic
├── results/        # Eval output, written to S3 before exit
├── main.py         # Entry point — orchestrates the full run
├── requirements.txt
└── .env            # API keys — never committed, injected at runtime
```

## Models tested

- Claude Sonnet 4.6
- Claude Haiku 4.5
- GPT-4o
- GPT-4o mini
- o1-mini
- o3-mini

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # add your API keys
python main.py
```

## Deployment

The repo is built into a Docker image and run as an ECS Fargate task. API keys are passed in as environment variables at runtime — never baked into the image.

```
Build image → push to ECR → RunTask on ECS → results written to S3 → container exits
```
