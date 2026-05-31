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
    "claude-opus-4-8":   "claude-opus-4-8",
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


# ── Mode helper ───────────────────────────────────────────────────────────────

# o3 always reasons (inherent reasoning model); gpt-4.1 / gpt-4.1-mini never do
# (not reasoning models). Claude models can do both, controlled by the flag.
REASONING_ONLY = {"o3", "o1", "o1-mini", "o3-mini"}
REGULAR_ONLY   = {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"}

def effective_mode(model: str, reasoning_requested: bool) -> str:
    """Resolve the actual mode a model runs in, given the requested flag."""
    if model in REASONING_ONLY:
        return "reasoning"
    if model in REGULAR_ONLY:
        return "regular"
    return "reasoning" if reasoning_requested else "regular"


# ── Claude agent ──────────────────────────────────────────────────────────────

# Reasoning budget matched to o3's ceiling for a fair comparison: o3 uses
# max_completion_tokens=50000, so Claude gets max_tokens=50000 with the thinking
# budget just under it (the rest covers the short final answer).
CLAUDE_MAX_TOKENS      = 50000
CLAUDE_THINKING_BUDGET = 45000

# Some newer Claude models reject thinking.type=enabled and require the adaptive
# form (thinking.type=adaptive + output_config.effort). We try enabled first and,
# on that specific 400, switch this model to adaptive for the rest of the run.
_CLAUDE_THINKING_STYLE = {}  # model -> "enabled" | "adaptive"

def _claude_reasoning_call(client, model, fen, mate_type, style):
    common = dict(
        model=model,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": build_user_prompt(fen, mate_type)}],
    )
    if style == "adaptive":
        common["thinking"] = {"type": "adaptive"}
        common["output_config"] = {"effort": "high"}
    else:  # enabled
        common["thinking"] = {"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET}
    with client.messages.stream(**common) as stream:
        return stream.get_final_message()


def query_claude(client: anthropic.Anthropic, model: str, fen: str, mate_type: str,
                 reasoning: bool) -> dict:
    import random
    for attempt in range(5):
        try:
            start = time.time()
            if reasoning:
                style = _CLAUDE_THINKING_STYLE.get(model, "enabled")
                try:
                    response = _claude_reasoning_call(client, model, fen, mate_type, style)
                except Exception as te:
                    msg = str(te)
                    # Wrong thinking form for this model: flip and retry once.
                    if style == "enabled" and "adaptive" in msg and "thinking" in msg:
                        _CLAUDE_THINKING_STYLE[model] = "adaptive"
                        print(" [switching to adaptive thinking]", flush=True)
                        response = _claude_reasoning_call(client, model, fen, mate_type, "adaptive")
                    else:
                        raise
            else:
                response = client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=[{"type": "text", "text": SYSTEM_PROMPT,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": build_user_prompt(fen, mate_type)}],
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

    # content may hold thinking block(s) before the text block; take the text block.
    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw = block.text
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
    # o3 and o1 use max_completion_tokens instead of max_tokens, and take a
    # reasoning_effort knob. We run at "high" to match Claude's high adaptive
    # effort for a fair maximum-effort-vs-maximum-effort comparison.
    if model in O3_MODELS:
        kwargs["max_completion_tokens"] = 50000  # room for reasoning + answer
        kwargs["reasoning_effort"] = "high"
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

def run_agent(puzzles: list, model: str, reasoning: bool = False) -> list:
    """
    Run the agent on a list of puzzles.

    Args:
        puzzles:   list of dicts with keys: PuzzleId, FEN, Solution, MateType, Tier, Rating
        model:     model name string (must be in ALL_MODELS)
        reasoning: request reasoning mode. Only affects Claude models; o3 always
                   reasons and gpt-4.1/mini never do (see effective_mode).

    Returns:
        list of result dicts with PuzzleId, model, predicted_moves, correct_moves, etc.
    """
    if model not in ALL_MODELS:
        raise ValueError(f"Unknown model: {model}. Choose from {ALL_MODELS}")

    is_claude = model in ANTHROPIC_MODELS
    mode = effective_mode(model, reasoning)
    print(f"  Mode: {mode}")

    if is_claude:
        # Longer timeout: extended thinking can make individual calls slow.
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=900.0)
    else:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=900.0)

    results = []

    for i, puzzle in enumerate(puzzles):
        puzzle_id = puzzle["PuzzleId"]
        fen       = puzzle["FEN"]
        solution  = puzzle["Solution"]
        mate_type = puzzle["MateType"]

        print(f"  [{i+1}/{len(puzzles)}] {puzzle_id} ({mate_type}) ...", end=" ", flush=True)

        try:
            if is_claude:
                response = query_claude(client, model, fen, mate_type, reasoning=(mode == "reasoning"))
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
