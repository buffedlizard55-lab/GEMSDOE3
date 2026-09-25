#!/usr/bin/env python3
"""Fail closed before CI/deployment: real TIFF, ZIP, raw field, independent mask, actual JS writer."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gems3.common import read_json, sha256  # noqa: E402
from gems3.raster import template_info, validate_submission  # noqa: E402


def check_published(docs=ROOT / "docs", run_browser=True):
    meta = read_json(docs / "data/submission.json")
    report = read_json(docs / "data/experiment.json")
    template = ROOT / "legacy/data/bridge/example_submission.tif"
    valid, _ = template_info(template)
    if sha256(template) != meta["template_sha256"]:
        raise ValueError("Published template hash mismatch")
    for key in ["artifact", "zip", "field", "mask"]:
        spec = meta[key]
        path = (docs / spec["file"]).resolve()
        if docs.resolve() not in path.parents:
            raise ValueError("Published path escapes the docs root")
        if not path.is_file() or path.stat().st_size != spec["bytes"] or sha256(path) != spec["sha256"]:
            raise ValueError(f"Changed/missing published {key}: {path}")
    if meta["artifact"]["sha256"] != report["artifact"]["sha256"]:
        raise ValueError("Artifact and experiment identities disagree")
    candidate = docs / meta["artifact"]["file"]
    checked = validate_submission(candidate, template)
    if not checked["passed"]:
        raise ValueError("Published candidate fails independently measured format gates")
    decoded = {}
    for key in ["field", "mask"]:
        spec = meta[key]
        raw = zlib.decompress((docs / spec["file"]).read_bytes())
        if len(raw) != spec["decoded_bytes"] or hashlib.sha256(raw).hexdigest() != spec["decoded_sha256"]:
            raise ValueError(f"Published {key} fails decompression/hash check")
        decoded[key] = raw
    mask = np.unpackbits(np.frombuffer(decoded["mask"], dtype="uint8"), bitorder="little")[:valid.size].reshape(valid.shape).astype(bool)
    if not np.array_equal(mask, valid):
        raise ValueError("Browser mask differs from actual reference mask")
    field = np.frombuffer(decoded["field"], dtype="<f4").reshape(valid.shape)
    with rasterio.open(candidate) as src:
        actual = src.read(1)
    if not np.array_equal(field, actual, equal_nan=True):
        raise ValueError("Browser field differs from published TIFF pixels")
    with zipfile.ZipFile(docs / meta["zip"]["file"]) as zipped:
        if zipped.namelist() != [meta["artifact"]["filename"]] or zipped.testzip() is not None:
            raise ValueError("Submission ZIP must contain exactly one intact TIFF")
        if hashlib.sha256(zipped.read(zipped.namelist()[0])).hexdigest() != meta["artifact"]["sha256"]:
            raise ValueError("ZIP contains different TIFF bytes")
    result = {"direct_tif": True, "zip": True, "field_bitwise_equivalent_except_nan_encoding": True,
              "mask_matches_reference": True, "artifact_sha256": meta["artifact"]["sha256"]}
    if run_browser:
        (ROOT / "outputs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs", prefix="browser-check-") as temp:
            target = Path(temp) / "browser.tif"
            run = subprocess.run(["node", str(ROOT / "scripts/build_browser_submission.cjs"),
                                  str(docs / "data/submission.json"), str(target)],
                                 check=True, capture_output=True, text=True, timeout=120, cwd=ROOT)
            browser = json.loads(run.stdout)
            if not browser["passed"]:
                raise ValueError("Exact browser JavaScript did not pass")
            browser_gate = validate_submission(target, template)
            if not browser_gate["passed"]:
                raise ValueError("Rasterio rejects TIFF from actual JavaScript writer")
            with rasterio.open(target) as generated:
                if not np.array_equal(generated.read(1), actual, equal_nan=True):
                    raise ValueError("Browser artifact changed model pixels")
            result["javascript_writer"] = browser
            result["independent_rasterio_validation"] = browser_gate
    return result


if __name__ == "__main__":
    print(json.dumps(check_published(), indent=2, allow_nan=False))
