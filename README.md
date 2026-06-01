# PuzzleChess Benchmark

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
| claude-opus-4-8 | Anthropic | Flagship |
| gpt-4.1-mini | OpenAI | Fast / cheap |
| gpt-4.1 | OpenAI | Mid |
| o3 | OpenAI | Reasoning |

Claude models can run with or without **extended thinking** (a reasoning toggle on the dashboard); the numbers below are the non-reasoning runs unless noted. **`claude-opus-4-8` is still being evaluated in reasoning mode** — its reasoning numbers are not final yet, so only its non-reasoning run is reported below.

## Results

📊 **[Full interactive dashboard → chess.adamissah.com](https://chess.adamissah.com)**

All models, 300 puzzles each, non-reasoning runs, sorted by accuracy. **Accuracy** counts a puzzle solved if the model produced the exact Lichess line **or** any valid alternate mate (see "How the verifier evolved" below). The **Exact** column is the strict exact-match rate.

| Model | Provider | Accuracy | Exact | Avg Score | Format Compliance | Avg Latency |
|---|---|---|---|---|---|---|
| **o3** | OpenAI | **76.0%** | 71.3% | 0.76 | 92% | 104s |
| claude-opus-4-8 | Anthropic | 10.7% | 10.7% | 0.40 | 93% | 14s |
| claude-opus-4-7 | Anthropic | 9.0% | 8.3% | 0.20 | 36% | 32s |
| gpt-4.1 | OpenAI | 6.7% | 6.3% | 0.36 | 87% | 0.8s |
| claude-sonnet-4-6 | Anthropic | 6.3% | 6.0% | 0.29 | 91% | 24s |
| claude-haiku-4-5 | Anthropic | 1.7% | 1.7% | 0.18 | 45% | 8s |
| gpt-4.1-mini | OpenAI | 1.7% | 1.7% | 0.27 | 84% | 1s |

### Headline finding

**o3 is in a different class: 76% vs. single digits for everyone else.** And it doesn't just score higher, it degrades *gracefully* with difficulty (mate-in-1 97% down to mate-in-5 53%; beginner 87% down to expert 59%) where every other model flatlines near 0% past mate-in-1. The reasoning model is doing actual lookahead; the rest are pattern-matching one-move mates.

**The qualitative edge that the numbers don't show:** o3 has a failure mode the others don't. When it genuinely can't find a forced mate, it **says so** (`"I'm sorry, I can't solve this"`) instead of inventing a plausible-looking wrong line. Its misses are mostly explicit refusals or last-move near-misses, not confident hallucinations. That's better-calibrated, safer behavior, a real difference in *kind*, not just degree.

**Among the non-reasoning models, output discipline beats raw search.** Opus 4.8 leads the pack (10.7%, composite 0.40) not by finding the most mates but by *returning them cleanly* — 93% format compliance and the highest legal-move rate (58%). Its predecessor Opus 4.7 finds nearly as many mates but spills them in loose, repeated moves (36% format compliance), so the eval can't credit work it actually did. Capability and usable output are different axes.

**Extended thinking did not help Claude here — it hurt.** Turning on the reasoning toggle collapsed format compliance for every Claude model evaluated so far (e.g. Sonnet 4.6 dropped from 91% to ~6%): the models think at length, blow past the output budget, and never emit a clean final line. The reasoning runs are kept on the dashboard for honesty, but the headline Claude numbers are the direct, non-reasoning runs. (**Opus 4.8's reasoning run is still in progress** — its reasoning result is excluded until that run completes.)

### How the verifier evolved

The accuracy number is only as trustworthy as the checker behind it, and getting that checker right took three passes — including catching an over-correction of my own.

1. **Exact match.** v1 compared the model's full move sequence directly to Lichess's recorded solution. Simple, but it rejects any valid answer that isn't byte-for-byte the canonical line.
2. **Any legal sequence ending in mate (the over-correction).** Suspecting models were finding *other* valid mates that exact-match threw away, I accepted any line whose every move was legal and whose final position was checkmate. This **inflated** results — o3 jumped ~71% → ~86% — but it was an artifact: the check lets the model play *both sides*, reaching mate only because the opponent made cooperative, suboptimal replies a real defender never would. That isn't a forced mate.
3. **Match the forcing line, free the final move.** Lichess builds puzzles so the intermediate moves are the single forcing line (the defender's best replies are baked in), and only the final mating move may vary, since a mating position can have several legal mates. So the correct check is: match Lichess's line on every move *except the last*, then accept any legal mate at the final ply. This moved o3 71.3% → 76% — a smaller, honest correction.

**Why act 3 is correct and not arbitrary:** matching the intermediate moves guarantees the sequence was genuinely forcing, because those moves already encode the opponent's best defense — Lichess's line *is* the best-defense line. The final move is the only free variable because the mating position can admit multiple legal mates. That's why no full engine search at every ply is needed. The whole correction was applied by re-scoring the saved result JSON (`rescore.py`), so it cost zero additional model tokens.

### Per-model analysis

- **o3 (OpenAI, reasoning):** 76% accuracy (71.3% exact + 14 alternate mates), 92% format compliance, but ~104s/puzzle and ~16k output tokens. Genuine search, graceful difficulty curve, and the honest "I can't solve this" failure mode above. A different class of model at a real latency/cost premium.
- **claude-opus-4-8 (Anthropic, flagship):** the strongest non-reasoning model — 10.7% accuracy, the highest format compliance in the field bar none (93%), the highest legal-move rate (58%), at ~14s and only ~850 output tokens. Composite 0.40, the top non-reasoning score. It fixes Opus 4.7's central flaw: nearly the same raw ability, but it returns one clean line instead of spilling moves. _(Its **reasoning-mode** run is still in progress — those numbers will be added once it completes.)_
- **claude-opus-4-7 (Anthropic, flagship):** second-best non-reasoning accuracy (9.0% with alternate mates), yet the **lowest** format compliance (36%) and most tokens (~1,775), so its composite (0.20) sinks near the bottom. The clearest case of *capability undercut by output*: it finds mates but spills repeated/loose moves instead of a clean line.
- **gpt-4.1 (OpenAI, mid):** second-best non-reasoning composite (0.36) via efficiency: sub-second, ~25 output tokens, 87% format compliance. Fast and clean, hard capability ceiling.
- **claude-sonnet-4-6 (Anthropic, mid):** ~ties gpt-4.1 on accuracy (6.3%) with the highest format compliance short of o3/Opus 4.8 (91%). The most disciplined output among the mid models, but the extra deliberation (~24s) buys format reliability, not more solutions.
- **claude-haiku-4-5 (Anthropic, fast):** same accuracy as gpt-4.1-mini (1.7%) but ~8× slower with only 45% format compliance despite ~900 tokens. Reasons at length, rarely converges, and drifts out of clean UCI. The weakest cost/benefit in the field.
- **gpt-4.1-mini (OpenAI, fast):** the capability floor. Cheapest and fastest (~1s, ~95 tokens), solves ~8% of mate-in-1s and almost nothing longer. Can pattern-match a one-move mate; no real lookahead.

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
- **Correctness** (`correct`, 0/1) — solved if the predicted line is the **exact** Lichess solution (`exact_match`) **or** a valid **alternate mate** (`alt_mate`): same length, every move except the last matching the canonical line, and a different but still-legal checkmate on the final move. See "How the verifier evolved" above for why this is the right rule.
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
- `overall_accuracy` — % of puzzles solved (exact line or alternate mate)
- `exact_match_rate` — % solved by the exact Lichess line only
- `alt_mate_count` — puzzles credited via an alternate final mate
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
