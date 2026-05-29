"""
eval.py

Scores agent results for the PuzzleChess benchmark.

Scoring per puzzle:
  - Move validity: each predicted move checked against python-chess (per-move)
  - Correctness:   exact match of full move sequence (binary)
  - Score:         0.5 * correct + 0.4 * valid_ratio + 0.1 * (1 - normalized_latency)

Output: results/{model}_results.json
"""

import json
import os
import chess
from collections import defaultdict

MAX_LATENCY_MS = 30_000  # cap for latency normalization

# ── Move validation ───────────────────────────────────────────────────────────

def validate_moves(fen: str, predicted_moves: str) -> dict:
    """
    Apply each predicted UCI move to the board sequentially.
    Returns per-move validity and summary counts.
    """
    if not predicted_moves or not predicted_moves.strip():
        return {"move_validity": [], "valid_moves_count": 0}

    moves = predicted_moves.strip().split()
    move_validity = []

    try:
        board = chess.Board(fen)
    except Exception:
        return {"move_validity": [False] * len(moves), "valid_moves_count": 0}

    for move_uci in moves:
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                board.push(move)
                move_validity.append(True)
            else:
                move_validity.append(False)
                break  # stop applying after first illegal move
        except Exception:
            move_validity.append(False)
            break

    # pad remaining moves as False if we stopped early
    while len(move_validity) < len(moves):
        move_validity.append(False)

    return {
        "move_validity":    move_validity,
        "valid_moves_count": sum(move_validity),
    }


# ── Per-puzzle scoring ────────────────────────────────────────────────────────

def score_puzzle(puzzle: dict) -> dict:
    """
    Score a single puzzle result dict from run_agent().
    Returns the puzzle dict with scoring fields added.
    """
    fen            = puzzle["FEN"] if "FEN" in puzzle else ""
    predicted      = puzzle.get("predicted_moves", "")
    correct        = puzzle.get("correct_moves", "")
    latency_ms     = puzzle.get("latency_ms", MAX_LATENCY_MS)
    total_moves    = len(correct.strip().split()) if correct.strip() else 0

    # move validity
    validity       = validate_moves(fen, predicted)
    move_validity  = validity["move_validity"]
    valid_count    = validity["valid_moves_count"]
    valid_ratio    = round(valid_count / total_moves, 4) if total_moves > 0 else 0.0

    # correctness — exact match
    is_correct     = int(predicted.strip().split() == correct.strip().split())

    # latency component
    capped_latency = min(latency_ms, MAX_LATENCY_MS)
    norm_latency   = capped_latency / MAX_LATENCY_MS if capped_latency > 0 else 1.0
    latency_score  = 1 / norm_latency if norm_latency > 0 else 0.0
    # normalize latency_score to [0,1] — max is 1/epsilon, so we just cap contribution
    latency_contrib = min(latency_score / (MAX_LATENCY_MS), 1.0)

    score = round(
        0.5 * is_correct
        + 0.4 * valid_ratio
        + 0.1 * (1 - norm_latency),  # lower latency = higher score
        4
    )

    return {
        **puzzle,
        "move_validity":     move_validity,
        "valid_moves_count": valid_count,
        "total_moves":       total_moves,
        "valid_ratio":       valid_ratio,
        "correct":           is_correct,
        "score":             score,
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate(scored_puzzles: list) -> dict:
    """Compute summary stats across all scored puzzles."""
    n = len(scored_puzzles)
    if n == 0:
        return {}

    def avg(key):
        return round(sum(p[key] for p in scored_puzzles) / n, 4)

    # accuracy by tier
    tier_buckets = defaultdict(list)
    for p in scored_puzzles:
        tier_buckets[p.get("tier", "unknown")].append(p["correct"])

    accuracy_by_tier = {
        tier: round(sum(vals) / len(vals), 4)
        for tier, vals in tier_buckets.items()
    }

    # accuracy by mate type
    mate_buckets = defaultdict(list)
    for p in scored_puzzles:
        mate_buckets[p.get("mate_type", "unknown")].append(p["correct"])

    accuracy_by_mate_type = {
        mate: round(sum(vals) / len(vals), 4)
        for mate, vals in mate_buckets.items()
    }

    return {
        "total_puzzles":        n,
        "overall_accuracy":     avg("correct"),
        "avg_score":            avg("score"),
        "avg_valid_ratio":      avg("valid_ratio"),
        "avg_latency_ms":       avg("latency_ms"),
        "avg_input_tokens":     avg("input_tokens"),
        "avg_output_tokens":    avg("output_tokens"),
        "accuracy_by_tier":     accuracy_by_tier,
        "accuracy_by_mate_type": accuracy_by_mate_type,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def score_results(results: list) -> dict:
    """
    Takes the output of run_agent() and returns a fully scored results dict.
    This is what main.py calls.

    Args:
        results: list of per-puzzle dicts from run_agent()

    Returns:
        {
            "model":   str,
            "summary": { aggregated stats },
            "puzzles": [ scored puzzle dicts ]
        }
    """
    model = results[0]["model"] if results else "unknown"

    print(f"Scoring {len(results)} puzzles for {model}...")
    scored = [score_puzzle(p) for p in results]

    summary = aggregate(scored)

    print(f"  Overall accuracy: {summary.get('overall_accuracy', 0):.1%}")
    print(f"  Avg score:        {summary.get('avg_score', 0):.4f}")
    print(f"  Avg latency:      {summary.get('avg_latency_ms', 0):.0f}ms")

    return {
        "model":   model,
        "summary": summary,
        "puzzles": scored,
    }


def write_results(scored_dict: dict, output_dir: str = "results") -> str:
    """Write scored results to results/{model}_results.json."""
    os.makedirs(output_dir, exist_ok=True)
    model = scored_dict["model"].replace("/", "-")
    path = os.path.join(output_dir, f"{model}_results.json")
    with open(path, "w") as f:
        json.dump(scored_dict, f, indent=2)
    print(f"  Results written to {path}")
    return path
