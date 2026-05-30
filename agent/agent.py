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
    "claude-haiku-4-5":  "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus-4-7":   "claude-opus-4-7",
}

OPENAI_MODELS = {
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1":      "gpt-4.1",
    "o3":           "o3",
}

ALL_MODELS = list(ANTHROPIC_MODELS) + list(OPENAI_MODELS)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a chess engine. You output chess moves in UCI format only.

UCI format: source square + destination square. Examples: e2e4, g1f3, e1g1
Each move is exactly 4 characters (or 5 for pawn promotion e.g. e7e8q). Letters and numbers ONLY.
No +, no #, no x, no symbols of any kind. No algebraic notation. No explanations.

Your ANSWER line must contain only UCI moves separated by spaces — letters and numbers only."""


def build_user_prompt(fen: str, mate_type: str) -> str:
    board = chess.Board(fen)
    turn = "White" if board.turn == chess.WHITE else "Black"
    mate_in = int(mate_type.replace("mateIn", ""))
    total_moves = mate_in * 2 - 1  # mateIn1=1, mateIn2=3, mateIn3=5, etc.
    opponent = "Black" if turn == "White" else "White"
    return (
        f"FEN: {fen}\n"
        f"{turn} to move. Find checkmate in {mate_in} moves.\n"
        f"Output exactly {total_moves} UCI moves alternating: {turn} move, {opponent} response, {turn} move, and so on.\n"
        f"Think through the position, then end your response with this exact line:\n"
        f"ANSWER: <{total_moves} UCI moves>\n"
        f"Example for mateIn2 (3 moves): ANSWER: e2e4 d7d5 f1b5"
    )


def extract_uci_moves(text: str) -> str:
    """Extract UCI moves from the ANSWER: tag in model output."""
    import re

    # find the ANSWER: line
    match = re.search(r'ANSWER:\s*(.+)', text, re.IGNORECASE)
    answer_text = match.group(1).strip() if match else text

    # strip capture notation 'x' so g7xg6 becomes g7g6
    answer_text = re.sub(r'([a-h][1-8])x([a-h][1-8])', r'\1\2', answer_text.lower())

    # extract all UCI move tokens
    tokens = re.findall(r'[a-h][1-8][a-h][1-8][qrbn]?', answer_text)
    return " ".join(tokens)


# ── Claude agent ──────────────────────────────────────────────────────────────

def query_claude(client: anthropic.Anthropic, model: str, fen: str, mate_type: str) -> dict:
    import random
    for attempt in range(5):
        try:
            start = time.time()
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": build_user_prompt(fen, mate_type)},
                ],
            )
            latency_ms = int((time.time() - start) * 1000)
            break
        except Exception as e:
            err = str(e)
            if attempt < 4 and ("529" in err or "overloaded" in err.lower() or "Connection error" in err):
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f" [retrying in {wait:.1f}s: {type(e).__name__}]", flush=True)
                time.sleep(wait)
            else:
                raise
    raw = response.content[0].text
    return {
        "predicted_moves": extract_uci_moves(raw),
        "latency_ms":      latency_ms,
        "input_tokens":    response.usage.input_tokens,
        "output_tokens":   response.usage.output_tokens,
    }


# ── OpenAI agent ──────────────────────────────────────────────────────────────

O3_MODELS = {"o3", "o1", "o1-mini", "o3-mini"}  # models using max_completion_tokens

def query_openai(client: OpenAI, model: str, fen: str, mate_type: str) -> dict:
    import random
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(fen, mate_type)},
        ],
    }
    # o3 and o1 use max_completion_tokens instead of max_tokens
    if model in O3_MODELS:
        kwargs["max_completion_tokens"] = 16000  # o3 needs room for reasoning + answer
    else:
        kwargs["max_tokens"] = 4096

    # retry with backoff for rate limits
    for attempt in range(5):
        try:
            start = time.time()
            response = client.chat.completions.create(**kwargs)
            latency_ms = int((time.time() - start) * 1000)
            break
        except Exception as e:
            err = str(e)
            if attempt < 4 and ("429" in err or "Connection error" in err or "APIConnectionError" in err):
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f" [retrying in {wait:.1f}s: {type(e).__name__}]", flush=True)
                time.sleep(wait)
            else:
                raise

    msg = response.choices[0].message
    raw = msg.content or ""
    extracted = extract_uci_moves(raw)
    expected = int(mate_type.replace("mateIn", "")) * 2 - 1
    if len(extracted.split()) != expected:
        print(f"\nDEBUG MISMATCH (expected {expected} moves): {repr(raw)}\n")
    return {
        "predicted_moves": extracted,
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
            print(f"ERROR: {type(e).__name__}: {e}")

        results.append({
            "PuzzleId":        puzzle_id,
            "FEN":             fen,
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
