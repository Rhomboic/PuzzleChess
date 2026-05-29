"""
load_puzzles.py

Reads puzzles_filtered.csv and returns a list of clean puzzle dicts
ready to be passed to the agent.
"""

import csv

PUZZLES_FILE = "data/puzzles_filtered.csv"


def load_puzzles(filepath: str = PUZZLES_FILE) -> list:
    """
    Load filtered puzzles from CSV.

    Returns a list of dicts:
    {
        "PuzzleId": str,
        "FEN":      str,   # position after opponent's setup move
        "Solution": str,   # correct UCI moves space-separated
        "Rating":   int,
        "Tier":     str,   # beginner / intermediate / advanced / expert
        "MateType": str,   # mateIn1 .. mateIn5
        "Themes":   str,
        "GameUrl":  str,
    }
    """
    puzzles = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            puzzles.append({
                "PuzzleId": row["PuzzleId"],
                "FEN":      row["FEN"],
                "Solution": row["Solution"],
                "Rating":   int(row["Rating"]),
                "Tier":     row["Tier"],
                "MateType": row["MateType"],
                "Themes":   row["Themes"],
                "GameUrl":  row["GameUrl"],
            })
    return puzzles


if __name__ == "__main__":
    puzzles = load_puzzles()
    print(f"Loaded {len(puzzles)} puzzles\n")
    print("Sample puzzle:")
    for k, v in puzzles[0].items():
        print(f"  {k}: {v}")
