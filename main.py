"""
main.py

Entry point for the PuzzleChess benchmark container.

Each container runs one model, determined by the MODEL environment variable.
Loads 300 puzzles, runs the agent, scores results, writes to S3, and exits.

Usage (local):
    MODEL=claude-sonnet-4-6 python main.py

Environment variables:
    MODEL               — model to run (required)
    ANTHROPIC_API_KEY   — required for Claude models
    OPENAI_API_KEY      — required for OpenAI models
    S3_BUCKET           — S3 bucket for results (optional locally)
    S3_KEY_PREFIX       — S3 key prefix, e.g. "runs/2024-01-01/" (optional)
"""

import os
import sys
import boto3
from dotenv import load_dotenv

from data.load_puzzles import load_puzzles
from agent.agent import run_agent, ALL_MODELS
from eval.eval import score_results, write_results

PUZZLES_FILE = "data/puzzles_filtered.csv"


def upload_to_s3(local_path: str, model: str) -> None:
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("  S3_BUCKET not set — skipping S3 upload")
        return

    prefix = os.environ.get("S3_KEY_PREFIX", "")
    s3_key = f"{prefix}{model}_results.json"

    print(f"  Uploading to s3://{bucket}/{s3_key} ...")
    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket, s3_key)
    print(f"  Upload complete")


def main():
    load_dotenv()

    # ── Validate MODEL env var ─────────────────────────────────────────────────
    model = os.environ.get("MODEL")
    if not model:
        print("ERROR: MODEL environment variable is not set.")
        print(f"Choose from: {ALL_MODELS}")
        sys.exit(1)

    if model not in ALL_MODELS:
        print(f"ERROR: Unknown model '{model}'.")
        print(f"Choose from: {ALL_MODELS}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"PuzzleChess Benchmark")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # ── Load puzzles ───────────────────────────────────────────────────────────
    print(f"Loading puzzles from {PUZZLES_FILE}...")
    puzzles = load_puzzles(PUZZLES_FILE)
    print(f"  {len(puzzles)} puzzles loaded\n")

    # ── Run agent ──────────────────────────────────────────────────────────────
    print(f"Running agent ({model}) on {len(puzzles)} puzzles...")
    results = run_agent(puzzles, model)
    print()

    # ── Score results ──────────────────────────────────────────────────────────
    scored = score_results(results)
    print()

    # ── Write results locally ──────────────────────────────────────────────────
    local_path = write_results(scored)
    print()

    # ── Upload to S3 ───────────────────────────────────────────────────────────
    upload_to_s3(local_path, model)

    print(f"\n{'='*60}")
    print(f"Done. Model: {model}")
    print(f"  Accuracy: {scored['summary'].get('overall_accuracy', 0):.1%}")
    print(f"  Avg score: {scored['summary'].get('avg_score', 0):.4f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
