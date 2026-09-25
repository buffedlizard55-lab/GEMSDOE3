#!/usr/bin/env python3
"""Strict local format gate; nonzero exit on every invalid or unreadable submission."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems3.common import ROOT, write_json
from gems3.raster import validate_submission

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--template", type=Path, default=ROOT / "data/sample_submission.tif")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_submission(args.file, args.template)
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if report["passed"] else 1)
