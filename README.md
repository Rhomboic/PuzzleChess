# PuzzleChess

An LLM agent benchmark that evaluates how well AI models solve chess puzzles. Runs as an ephemeral Docker container on AWS ECS Fargate.

## What it does

1. Loads 300 filtered chess puzzles from a Lichess dataset (`data/`)
2. Sends each puzzle to an LLM agent (`agent/`) which outputs the correct move sequence in UCI notation
3. Scores the agent's answers against the correct solutions (`eval/`)
4. Writes results to S3 and exits

## Models tested

| Model | Provider | Tier |
|---|---|---|
| claude-haiku-4-5-20251001 | Anthropic | Fast / cheap |
| claude-sonnet-4-6 | Anthropic | Mid |
| claude-opus-4-7 | Anthropic | Flagship |
| gpt-4.1-mini | OpenAI | Fast / cheap |
| gpt-4.1 | OpenAI | Mid |
| o3 | OpenAI | Reasoning |

## Results

📊 **[View full benchmark results and interactive charts → chess.adamissah.com](https://chess.adamissah.com)**

## Project structure

```
PuzzleChess/
├── data/
│   ├── filter_puzzles.py   # Filters Lichess CSV → 300 puzzles across 5 mate types × 4 tiers
│   ├── load_puzzles.py     # Loads puzzles into dicts for the agent
│   └── puzzles_filtered.csv
├── agent/
│   └── agent.py            # LLM agent loop (Claude + OpenAI, all 6 models)
├── eval/
│   └── eval.py             # Scoring: correctness, move validity, format compliance, latency
├── terraform/              # AWS infra as code (ECR, ECS, S3, IAM, Secrets Manager)
├── results/                # Eval output JSON, written to S3 before container exits
├── main.py                 # Entry point — orchestrates the full run
├── Dockerfile              # One image per model (MODEL baked in via ARG)
├── push_images.sh          # Build and push all 6 images to ECR
└── run_fargate.sh          # Launch all 6 ECS tasks in parallel
```

## Eval metrics

Each puzzle's model output is parsed (UCI tokens are extracted from the response, stripping any stray `+`, `#`, `x`, or reasoning text) and scored on:

**Per-puzzle metrics**
- **Correctness** (`correct`, 0/1) — does the full predicted move sequence exactly match the puzzle's solution?
- **Move validity** (`move_validity`, per-move list) — each predicted move is applied to the board with `python-chess`; a move is valid only if it is legal in the resulting position. Stops at the first illegal move.
- **Valid ratio** (`valid_ratio`) — `valid_moves_count / total_moves`. Partial credit for producing legal moves even when the full line is wrong.
- **Output format followed** (`output_format_followed`, 0/1) — did the model produce exactly the expected number of **well-formed UCI moves** (source+destination squares, e.g. `e2e4`, plus promotion suffix where needed)? Because non-UCI output (algebraic like `Rxf8#`, prose, wrong move counts) is stripped during parsing, this metric captures both **notation correctness** and **sequence length** — anything that isn't clean UCI fails to reach the expected count.
- **Latency** (`latency_ms`) — wall-clock time of the API call.
- **Token usage** (`input_tokens`, `output_tokens`) — reported by each provider's API.

**Composite score**
```
score = 0.45 * correct
      + 0.35 * valid_ratio
      + 0.10 * (1 - normalized_latency)   # normalized against a 30s cap
      + 0.10 * output_format_followed
```

**Aggregate metrics (per model)**
- `overall_accuracy` — % of puzzles solved exactly
- `avg_score` — mean composite score
- `avg_valid_ratio` — mean legal-move ratio
- `format_compliance_rate` — % of puzzles where output format was followed
- `avg_latency_ms`, `avg_input_tokens`, `avg_output_tokens`
- `accuracy_by_tier` — beginner / intermediate / advanced / expert
- `accuracy_by_mate_type` — mateIn1 … mateIn5

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # add your API keys and MODEL name
python main.py
```

## Deployment

Each model runs in its own Docker container on AWS ECS Fargate. API keys are stored in AWS Secrets Manager and injected at container startup — never baked into the image.

```
terraform apply          # provision ECR, ECS, S3, IAM, Secrets Manager
./push_images.sh         # build linux/amd64 images and push to ECR
./run_fargate.sh         # launch all 6 tasks in parallel
```

Results appear in S3 as each container finishes:
```
s3://puzzlechess-results-{account_id}/runs/{model}_results.json
```
