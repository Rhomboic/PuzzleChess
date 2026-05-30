# PuzzleChess — Project Notes for Interview Prep

## What is this project?

A benchmarking system that evaluates how well LLM models solve chess puzzles.
The agent is given a board position (FEN) and must find the correct checkmate sequence.
Six models are tested across 300 puzzles, scored on correctness, move validity, output format compliance, and latency.

This mirrors what Fleet AI does — building environments and eval harnesses that measure AI agent performance systematically.

---

## Why chess puzzles?

Chess puzzles have a single correct answer — this makes evaluation objective and automated. No LLM-as-judge needed for correctness. The eval harness can compare the model's move sequence against the known solution exactly.

---

## The Data Pipeline

**Source:** Lichess open puzzle database (~6 million puzzles)

**Format per puzzle:**
```
PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags
```

**Key insight about the FEN and Moves fields:**
- The FEN is the board position BEFORE the opponent's setup move
- `Moves[0]` is the opponent's setup move — we apply this to get the actual puzzle position
- `Moves[1:]` is the correct solution the agent needs to find
- We use `python-chess` to apply the setup move and derive a new FEN

**Filtering:**
- Only mate puzzles: mateIn1, mateIn2, mateIn3, mateIn4, mateIn5
- 4 rating tiers: Beginner (<1200), Intermediate (1200-1600), Advanced (1600-2000), Expert (2000+)
- 15 puzzles per bucket × 5 mate types × 4 tiers = **300 puzzles total**
- Evenly distributed so results are comparable across difficulty

---

## The Agent

**Models tested:**
| Model | Provider | Tier |
|---|---|---|
| claude-haiku-4-5-20251001 | Anthropic | Fast/cheap |
| claude-sonnet-4-6 | Anthropic | Mid |
| claude-opus-4-7 | Anthropic | Flagship |
| gpt-4.1-mini | OpenAI | Fast/cheap |
| gpt-4.1 | OpenAI | Mid |
| o3 | OpenAI | Reasoning |

**Prompt design:**
- System prompt: strict UCI-only output instructions, no symbols, no algebraic notation
- User prompt: FEN position, whose turn, how many moves to find, exact move count including opponent responses
- `ANSWER:` tag pattern so the model can reason freely but we extract only the final answer
- Example: for mateIn3 (5 total moves): `ANSWER: h7g7 g8h8 d1h1 e4h4 h1h4`

**Key prompt engineering decisions:**
1. We tell the model the EXACT number of moves to output (2N-1 for mateInN)
2. We specify alternating format: "your move, opponent response, your move..."
3. `ANSWER:` tag lets the model reason before committing — we only parse the tag
4. Regex handles edge cases: `+`/`#` notation suffixes, `x` capture notation, concatenated moves

**Prompt caching (Claude):**
- System prompt is marked `cache_control: ephemeral`
- Anthropic caches it across 300 calls — saves significant cost on repeated system prompt tokens

---

## The Eval Harness

**Per-puzzle metrics:**
- `correct` — exact match of full move sequence (binary 0/1)
- `move_validity` — per-move list of whether each move is legal on the board (via python-chess)
- `valid_ratio` — valid_moves / total_moves
- `output_format_followed` — did the model return the expected number of UCI moves?
- `latency_ms` — wall clock of the API call
- `input_tokens` / `output_tokens` — from the API response

**Scoring formula:**
```
score = 0.45 * correct
      + 0.35 * valid_ratio
      + 0.10 * (1 - normalized_latency)
      + 0.10 * output_format_followed
```

Correctness is the dominant signal (0.45). Valid ratio gives partial credit for models that play legal but wrong moves. Format compliance catches models that ignore output instructions entirely.

**Aggregation per model:**
- Overall accuracy
- Accuracy by tier (beginner → expert)
- Accuracy by mate type (mateIn1 → mateIn5)
- Format compliance rate
- Avg latency, avg tokens

---

## Architecture

```
Local machine
├── data/filter_puzzles.py     → filters Lichess CSV → puzzles_filtered.csv
├── data/load_puzzles.py       → loads puzzles into dicts for the agent
├── agent/agent.py             → LLM agent loop (Claude + OpenAI)
├── eval/eval.py               → scoring logic
├── main.py                    → entry point: load → agent → eval → S3
├── Dockerfile                 → one image per model (MODEL baked in via ARG)
└── terraform/                 → all AWS infra as code

AWS
├── ECR                        → stores 6 Docker images (one per model)
├── ECS Fargate                → runs 6 containers in parallel (no EC2 to manage)
├── S3                         → stores results JSON per model
├── Secrets Manager            → stores API keys (never in code or Terraform state)
├── IAM                        → task execution role + task role (least privilege)
└── CloudWatch                 → container logs
```

**Container design:**
- Each of the 6 models has its own Docker image with `MODEL` baked in at build time
- API keys are injected at runtime from AWS Secrets Manager — ECS fetches them automatically
- Container runs: load puzzles → agent solves → eval scores → write to S3 → exit
- All 6 run in parallel on Fargate — no EC2 to provision or manage

---

## Key Engineering Decisions

**Why Fargate over EC2?**
The containers are ephemeral — spin up, run, exit. Fargate is perfect for this: no servers to manage, pay only for runtime, and tasks can run in parallel trivially.

**Why one container per model?**
Clean isolation. Each model is a separate benchmark run. If one fails it doesn't affect others. Also mirrors how you'd run this in production — parallel, independent, scalable.

**Why Secrets Manager over .env?**
API keys should never be in the image or Terraform state. Secrets Manager lets ECS inject them at runtime as env vars — your Python code sees `os.environ["ANTHROPIC_API_KEY"]` as normal, nothing changes in app code.

**Why python-chess for move validation?**
It handles FEN parsing, legal move generation, and move application correctly. Applying moves to validate legality is the ground truth — we don't need Stockfish for this.

**Why the ANSWER: tag?**
Reasoning models (Claude Sonnet, o3) think out loud before answering. Without a structured tag, the reasoning text contaminates the output. The tag lets the model reason freely while giving us a reliable extraction point.

---

## Results So Far (partial — sonnet, opus, o3 still running)

> ⚠️ TODO: Update this table tomorrow once all 6 model runs complete. Also update accuracy_by_tier and accuracy_by_mate_type breakdowns and write the full analysis section.

| Model | Accuracy | Format Compliance | Avg Latency |
|---|---|---|---|
| gpt-4.1-mini | 2.3% | ~80% | 1,193ms |
| gpt-4.1 | 6.7% | 86.3% | 881ms |
| o3 | TBD (running) | TBD | ~100-300s |
| claude-haiku-4-5 | TBD | TBD | ~9s |
| claude-sonnet-4-6 | TBD | TBD | ~27s |
| claude-opus-4-7 | TBD | TBD | TBD |

**Early observations:**
- gpt-4.1 is 3x more accurate than gpt-4.1-mini (6.7% vs 2.3%)
- Both OpenAI models score ~26% on mateIn1 but near 0% on longer sequences
- o3 appears to be solving expert-rated puzzles correctly but occasionally refuses intermediate ones (interesting failure mode)
- Format compliance is a real signal — some models output algebraic notation despite strict instructions

---

## Interesting Problems We Solved

**The FEN update problem:** The Lichess CSV has the position before the opponent's setup move. We had to apply `Moves[0]` to get the actual puzzle position using `python-chess` before passing it to the agent.

**The reasoning model problem:** Claude and o3 reason out loud, contaminating the output. We solved this with the `ANSWER:` tag pattern and a regex that extracts only UCI tokens from the tagged line.

**The notation problem:** Models output `Rd8+`, `f7f6#`, `g7xg6` despite being told not to. We handle this in `extract_uci_moves` by stripping `+`, `#`, and `x` before extracting valid 4-character UCI patterns.

**The o3 token problem:** o3 uses all its `max_completion_tokens` for internal reasoning, leaving nothing for the actual answer. Solution: set `max_completion_tokens=50000` so there's always room for both reasoning and output.

**The platform problem:** Docker images built on Apple Silicon (arm64) won't run on Fargate (amd64). Fixed by adding `--platform linux/amd64` to all builds.

---

## How to Talk About This at Fleet AI

**The one-liner:**
> "I built a benchmarking system that evaluates LLM performance on chess puzzles across difficulty tiers. The eval harness runs 300 puzzles across 6 models in parallel on AWS ECS Fargate, scoring correctness, move legality, format compliance, and latency. Each model runs in its own container deployed via Terraform, with results written to S3."

**What makes it interesting:**
- The eval is automated and objective — no human labeling needed
- Multi-dimensional scoring, not just pass/fail
- Format compliance as a metric captures prompt instruction-following ability
- The infrastructure is production-grade: containers, Fargate, Secrets Manager, Terraform IaC

**What you learned:**
- How to design a prompt for structured output from reasoning models
- How ECS Fargate task definitions work, including secrets injection
- How Terraform provisions cloud resources and how outputs connect scripts to infra
- The difference between arm64 (Mac) and amd64 (cloud) and why it matters for Docker
