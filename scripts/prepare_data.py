#!/usr/bin/env python3
"""Validate the entire pinned input set and record machine-readable evidence."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems3.common import ROOT, write_json
from gems3.data import inspect_data

if __name__ == "__main__":
    report = inspect_data()
    write_json(ROOT / "evidence/data.json", report)
    print(f"PASS: {len(report['files'])} hash-pinned files, {len(report['bands'])} bands; "
          f"{report['valid_pixels']:,} valid pixels. See evidence/data.json for irregularities.")
