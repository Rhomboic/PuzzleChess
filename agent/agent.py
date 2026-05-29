"""
agent.py

Sends chess puzzles to an LLM and collects its move responses.
Supports Claude (Anthropic) and OpenAI models.
"""

import os
import time
import chess
import anthropic
from openai import OpenAI

# ── Model registry ────────────────────────────────────────────────────────────

ANTHROPIC_MODELS = {
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-haiku-4-5":  "claude-haiku-4-5",
}

OPENAI_MODELS = {
    "gpt-4o":      "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "o1-mini":     "o1-mini",
    "o3-mini":     "o3-mini",
}

ALL_MODELS = list(ANTHROPIC_MODELS) + list(OPENAI_MODELS)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a chess engine. You will be given a chess position in FEN notation and told whose turn it is to move.

Your job is to find the checkmate sequence.

Rules:
- Output ONLY the moves in UCI notation, separated by spaces (e.g. e2e4 d7d5 f1c4)
- Do not explain, do not use algebraic notation, do not add any other text
- UCI format is: source square + destination square (e.g. e2e4, g1f3, e1g1 for castling)
- Output exactly the number of moves needed to deliver checkmate"""


def build_user_prompt(fen: str, mate_type: str) -> str:
    board = chess.Board(fen)
    turn = "White" if board.turn == chess.WHITE else "Black"
    mate_in = mate_type.replace("mateIn", "")
    return (
        f"Position (FEN): {fen}\n"
        f"It is {turn}'s turn to move.\n"
        f"Find the checkmate in {mate_in} moves.\n"
        f"Output only the UCI moves:"
    )


# ── Claude agent ──────────────────────────────────────────────────────────────

def query_claude(client: anthropic.Anthropic, model: str, fen: str, mate_type: str) -> dict:
    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=64,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # cache system prompt across calls
            }
        ],
        messages=[
            {"role": "user", "content": build_user_prompt(fen, mate_type)}
        ],
    )
    latency_ms = int((time.time() - start) * 1000)
    return {
        "predicted_moves": response.content[0].text.strip(),
        "latency_ms":      latency_ms,
        "input_tokens":    response.usage.input_tokens,
        "output_tokens":   response.usage.output_tokens,
    }


# ── OpenAI agent ──────────────────────────────────────────────────────────────

def query_openai(client: OpenAI, model: str, fen: str, mate_type: str) -> dict:
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        max_tokens=64,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(fen, mate_type)},
        ],
    )
    latency_ms = int((time.time() - start) * 1000)
    return {
        "predicted_moves": response.choices[0].message.content.strip(),
        "latency_ms":      latency_ms,
        "input_tokens":    response.usage.prompt_tokens,
        "output_tokens":   response.usage.completion_tokens,
    }


# ── Main agent loop ───────────────────────────────────────────────────────────

def run_agent(puzzles: list, model: str) -> list:
    """
    Run the agent on a list of puzzles.

    Args:
        puzzles: list of dicts with keys: PuzzleId, FEN, Solution, MateType, Tier, Rating
        model:   model name string (must be in ALL_MODELS)

    Returns:
        list of result dicts with PuzzleId, model, predicted_moves, correct_moves, etc.
    """
    if model not in ALL_MODELS:
        raise ValueError(f"Unknown model: {model}. Choose from {ALL_MODELS}")

    is_claude = model in ANTHROPIC_MODELS

    if is_claude:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    else:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    results = []

    for i, puzzle in enumerate(puzzles):
        puzzle_id = puzzle["PuzzleId"]
        fen       = puzzle["FEN"]
        solution  = puzzle["Solution"]
        mate_type = puzzle["MateType"]

        print(f"  [{i+1}/{len(puzzles)}] {puzzle_id} ({mate_type}) ...", end=" ", flush=True)

        try:
            if is_claude:
                response = query_claude(client, model, fen, mate_type)
            else:
                response = query_openai(client, model, fen, mate_type)
            print(f"-> {response['predicted_moves']} ({response['latency_ms']}ms)")
        except Exception as e:
            response = {"predicted_moves": "", "latency_ms": 0, "input_tokens": 0, "output_tokens": 0}
            print(f"ERROR: {e}")

        results.append({
            "PuzzleId":        puzzle_id,
            "model":           model,
            "predicted_moves": response["predicted_moves"],
            "correct_moves":   solution,
            "mate_type":       mate_type,
            "tier":            puzzle.get("Tier", ""),
            "rating":          puzzle.get("Rating", ""),
            "latency_ms":      response["latency_ms"],
            "input_tokens":    response["input_tokens"],
            "output_tokens":   response["output_tokens"],
        })

    return results
