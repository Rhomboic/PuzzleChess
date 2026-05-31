"""
rescore.py

Re-score saved benchmark results with the current eval logic WITHOUT re-running any
models (no token spend). The eval credits alternative mates: an answer that
reproduces the Lichess solution exactly except for the final move, where the
different final move is still a legal checkmate, counts as correct (Lichess accepts
any mate on the last move). Intermediate moves must match the forced solution.

This script reads the ORIGINAL result files (`{model}_results.json`,
`{model}_reasoning_results.json`) and writes NEW, separately-tagged files
(`{model}_alternate_mate_results.json`, `{model}_alternate_mate_reasoning_results.json`).
The originals are never modified. Each tagged file carries BOTH numbers in its
summary: `exact_match_rate` (original, exact-match-only accuracy) and
`overall_accuracy` (accuracy when alternative final mates are accepted).

Usage:
  python rescore.py --pull            # sync originals from S3, rescore, write tagged files locally
  python rescore.py                   # rescore originals already in results/, write tagged files
  python rescore.py --pull --upload   # also upload the tagged files to S3 (originals untouched)

Flags:
  --pull       aws s3 sync the original *_results.json files from S3 into results/ first
  --upload     upload the tagged files to S3 (implies writing locally)
  --no-mirror  skip mirroring tagged files into dashboard/results/

Reads S3_BUCKET / S3_KEY_PREFIX from the environment (.env supported). manifest.json
is never modified (the tagged files reuse the same model/mode naming convention).
"""

import os
import sys
import json
import glob
import subprocess

from dotenv import load_dotenv

from eval.eval import score_results

RESULTS_DIR = "results"
MIRROR_DIR = "dashboard/results"
TAG = "_alternate_mate"


def tagged_name(filename: str) -> str:
    """`{model}_results.json`          -> `{model}_alternate_mate_results.json`
       `{model}_reasoning_results.json`-> `{model}_alternate_mate_reasoning_results.json`
    The tag is inserted before the mode/results suffix so the dashboard can build
    the name as `${key}${TAG}_results.json` / `${key}${TAG}_reasoning_results.json`."""
    base = os.path.basename(filename)
    if base.endswith("_reasoning_results.json"):
        stem = base[: -len("_reasoning_results.json")]
        return f"{stem}{TAG}_reasoning_results.json"
    if base.endswith("_results.json"):
        stem = base[: -len("_results.json")]
        return f"{stem}{TAG}_results.json"
    return base


def pull_from_s3(bucket: str, prefix: str) -> None:
    """Pull only the ORIGINAL (untagged) result files."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    src = f"s3://{bucket}/{prefix}"
    print(f"Pulling original results from {src} -> {RESULTS_DIR}/ ...")
    subprocess.run(
        ["aws", "s3", "sync", src, RESULTS_DIR,
         "--exclude", "*", "--include", "*_results.json",
         "--exclude", f"*{TAG}*"],  # never pull previously-tagged files back as sources
        check=True,
    )


def rescore_to_tagged(src_path: str):
    """Re-score one original results JSON and write a tagged copy.
    Returns (tagged_filename, exact_match_rate, with_alt_accuracy, alt_count)."""
    with open(src_path) as f:
        data = json.load(f)
    rescored = score_results(data.get("puzzles", []))
    s = rescored["summary"]
    out_name = tagged_name(src_path)
    out_path = os.path.join(RESULTS_DIR, out_name)
    with open(out_path, "w") as f:
        json.dump(rescored, f, indent=2)
    return (
        out_name,
        s.get("exact_match_rate"),
        s.get("overall_accuracy"),
        s.get("alt_mate_count", 0),
    )


def main():
    load_dotenv()
    do_pull = "--pull" in sys.argv
    do_upload = "--upload" in sys.argv
    do_mirror = "--no-mirror" not in sys.argv

    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_KEY_PREFIX", "")

    if do_pull:
        if not bucket:
            sys.exit("S3_BUCKET not set — cannot --pull")
        pull_from_s3(bucket, prefix)

    # Source = original (untagged) files only.
    paths = sorted(
        p for p in glob.glob(os.path.join(RESULTS_DIR, "*_results.json"))
        if TAG not in os.path.basename(p)
    )
    if not paths:
        sys.exit(f"No original *_results.json files in {RESULTS_DIR}/ (run with --pull first?)")

    fmt = lambda v: f"{v:.4f}" if isinstance(v, (int, float)) else str(v)
    rows = []

    for src_path in paths:
        out_name, exact, with_alt, alt = rescore_to_tagged(src_path)
        rows.append((out_name, exact, with_alt, alt))

        out_path = os.path.join(RESULTS_DIR, out_name)
        if do_mirror:
            os.makedirs(MIRROR_DIR, exist_ok=True)
            with open(out_path) as src, open(os.path.join(MIRROR_DIR, out_name), "w") as dst:
                dst.write(src.read())
        if do_upload:
            if not bucket:
                sys.exit("S3_BUCKET not set — cannot --upload")
            key = f"{prefix}{out_name}"
            subprocess.run(["aws", "s3", "cp", out_path, f"s3://{bucket}/{key}"], check=True)

    print("\n" + "=" * 84)
    print(f"{'tagged file':<52} {'exact':>8} {'+alt':>8} {'alt_mate':>9}")
    print("-" * 84)
    total_alt = 0
    for name, exact, with_alt, alt in rows:
        total_alt += alt or 0
        print(f"{name:<52} {fmt(exact):>8} {fmt(with_alt):>8} {alt:>9}")
    print("-" * 84)
    print(f"{'TOTAL newly-credited alternative mates':<70} {total_alt:>9}")
    print("=" * 84)

    # Machine-readable report for reliable inspection.
    with open(os.path.join(RESULTS_DIR, "_rescore_report.json"), "w") as f:
        json.dump(
            [{"file": n, "exact_match_rate": e, "overall_accuracy": w, "alt_mate_count": a}
             for n, e, w, a in rows],
            f, indent=2,
        )

    if not do_upload:
        print("\n(local only — tagged files written to results/"
              + (" and dashboard/results/" if do_mirror else "")
              + ". Use --upload to push them to S3; originals are never modified.)")


if __name__ == "__main__":
    main()
