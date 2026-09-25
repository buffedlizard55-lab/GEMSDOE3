#!/usr/bin/env python3
"""Record a platform response for one published file, so no result lives in someone's memory.

The project rule is that a score is meaningless without the submission it belongs to. This script is
the only supported way to add a competition result to `evidence/leaderboard-results.json`:

* it refuses a score without a submission id,
* it refuses a file that is not in the published portfolio (so the record points at a real artifact),
* it refuses to overwrite an existing id,
* it stores the file's SHA-256 next to the record, because filenames change and hashes do not.

Example (after the platform returns a submission id and a public score):

    python scripts/record_submission.py \\
        --file docs/downloads/pindrop-v4-nodes-<stamp>-<hash>.tif \\
        --submission-id 1234567 --score 0.3123 --status accepted \\
        --message "Submission scored successfully"

Nothing here uploads anything and nothing here guesses a score.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gems3.common import read_json, sha256, utc_now, write_json  # noqa: E402

RESULTS = ROOT / "evidence/leaderboard-results.json"


def load_results() -> dict:
    if RESULTS.exists():
        return read_json(RESULTS)
    return {"schema_version": 1, "scope": "platform responses for published files; no inferred scores",
            "records": []}


def find_in_portfolio(path: Path, docs: Path = ROOT / "docs") -> dict:
    manifest_path = docs / "data/portfolio.json"
    if not manifest_path.exists():
        raise SystemExit("No published portfolio manifest; publish a portfolio before recording a result")
    manifest = read_json(manifest_path)
    resolved = path.resolve()
    for item in manifest["items"]:
        if (docs / item["file"]).resolve() == resolved:
            return {"strategy": manifest["strategy"], "variant": item["variant"], "note": item["note"],
                    "manifest_published_at": manifest["published_at"]}
    raise SystemExit(f"{path} is not one of the published portfolio files; refusing to record it")


def record(path: Path, submission_id: str, score: float | None, status: str, message: str) -> dict:
    if not str(submission_id).strip():
        raise SystemExit("A submission id is required: an account-level score alone cannot be attributed")
    if score is not None and not 0.0 <= score <= 1.0:
        raise SystemExit("A public score must be inside [0, 1]")
    results = load_results()
    if any(str(r["submission_id"]) == str(submission_id) for r in results["records"]):
        raise SystemExit(f"Submission id {submission_id} is already recorded; edit the file deliberately")
    entry = {"recorded_at": utc_now(), "submission_id": str(submission_id), "status": status,
             "score": score, "platform_message": message, "file": str(path.relative_to(ROOT)),
             "filename": path.name, "sha256": sha256(path), **find_in_portfolio(path)}
    results["records"].append(entry)
    scored = [r["score"] for r in results["records"] if r["score"] is not None]
    results["summary"] = {
        "records": len(results["records"]),
        "scored": len(scored),
        "best_public_score": max(scored) if scored else None,
        "best_record": (max((r for r in results["records"] if r["score"] is not None),
                            key=lambda r: r["score"]) if scored else None),
        "note": "Account-level leaderboard observations are not substituted for these records.",
    }
    write_json(RESULTS, results)
    print(json.dumps(entry, indent=2))
    print(f"\nRecorded {len(results['records'])} submission response(s) in {RESULTS.relative_to(ROOT)}")
    return entry


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, required=True, help="published .tif that was uploaded")
    ap.add_argument("--submission-id", required=True, help="the platform's submission id (required)")
    ap.add_argument("--score", type=float, default=None, help="public score if one was returned")
    ap.add_argument("--status", default="accepted", choices=["accepted", "rejected", "pending", "error"])
    ap.add_argument("--message", default="", help="the platform's own wording, quoted verbatim")
    args = ap.parse_args()
    if not args.file.is_file():
        raise SystemExit(f"{args.file} does not exist")
    record(args.file.resolve(), args.submission_id, args.score, args.status, args.message)


if __name__ == "__main__":
    main()
