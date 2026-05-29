"""
filter_puzzles.py

Reads the raw Lichess puzzle CSV, filters for mate puzzles, applies the
opponent's setup move to each FEN, and samples 300 puzzles evenly across
5 mate types × 4 rating tiers.

Output: data/puzzles_filtered.csv
"""

import csv
import random
import chess
from collections import defaultdict
from typing import Optional

INPUT_FILE = "data/lichess_db_puzzle.csv"
OUTPUT_FILE = "data/puzzles_filtered.csv"

MATE_TYPES = ["mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5"]

RATING_TIERS = [
    ("beginner",     0,    1200),
    ("intermediate", 1200, 1600),
    ("advanced",     1600, 2000),
    ("expert",       2000, 9999),
]

PUZZLES_PER_BUCKET = 15  # 5 mate types × 4 tiers × 15 = 300


def get_mate_type(themes: str) -> Optional[str]:
    for mate in MATE_TYPES:
        if mate in themes:
            return mate
    return None


def get_rating_tier(rating: int) -> Optional[str]:
    for name, low, high in RATING_TIERS:
        if low <= rating < high:
            return name
    return None


def apply_setup_move(fen: str, uci_move: str) -> Optional[str]:
    try:
        board = chess.Board(fen)
        board.push_uci(uci_move)
        return board.fen()
    except Exception:
        return None


def main():
    # buckets keyed by (mate_type, rating_tier)
    buckets = defaultdict(list)

    print(f"Reading {INPUT_FILE}...")
    with open(INPUT_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            themes = row["Themes"]
            mate_type = get_mate_type(themes)
            if not mate_type:
                continue

            try:
                rating = int(row["Rating"])
            except ValueError:
                continue

            tier = get_rating_tier(rating)
            if not tier:
                continue

            bucket_key = (mate_type, tier)
            # skip overfull buckets early to avoid storing millions of rows
            if len(buckets[bucket_key]) >= PUZZLES_PER_BUCKET * 10:
                continue

            moves = row["Moves"].strip().split()
            if len(moves) < 2:
                continue  # need at least setup move + one solution move

            setup_move = moves[0]
            solution = moves[1:]

            puzzle_fen = apply_setup_move(row["FEN"], setup_move)
            if not puzzle_fen:
                continue

            buckets[bucket_key].append({
                "PuzzleId":   row["PuzzleId"],
                "FEN":        puzzle_fen,
                "Solution":   " ".join(solution),
                "Rating":     rating,
                "Tier":       tier,
                "MateType":   mate_type,
                "Themes":     themes,
                "GameUrl":    row["GameUrl"],
            })

    print("Sampling puzzles...")
    sampled = []
    for mate_type in MATE_TYPES:
        for tier_name, _, _ in RATING_TIERS:
            key = (mate_type, tier_name)
            pool = buckets[key]
            if len(pool) < PUZZLES_PER_BUCKET:
                print(f"  WARNING: only {len(pool)} puzzles for {key}, wanted {PUZZLES_PER_BUCKET}")
            picked = random.sample(pool, min(PUZZLES_PER_BUCKET, len(pool)))
            sampled.extend(picked)
            print(f"  {key}: {len(picked)} puzzles")

    random.shuffle(sampled)

    print(f"\nWriting {len(sampled)} puzzles to {OUTPUT_FILE}...")
    fieldnames = ["PuzzleId", "FEN", "Solution", "Rating", "Tier", "MateType", "Themes", "GameUrl"]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sampled)

    print("Done.")
    print(f"\nBreakdown:")
    for mate_type in MATE_TYPES:
        for tier_name, _, _ in RATING_TIERS:
            count = sum(1 for p in sampled if p["MateType"] == mate_type and p["Tier"] == tier_name)
            print(f"  {mate_type:10} | {tier_name:12} | {count} puzzles")


if __name__ == "__main__":
    main()
