"""Hash-pinned, resumable-by-file data placement and measurement. No authentication bypass."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
import requests

from .common import ROOT, read_json, sha256, utc_now, write_json
from .raster import template_info

UPSTREAM_COMMIT = "cceebbdcf9a7d2890bb0665defcb54dfc66ae452"
BRIDGE = ROOT / "legacy/data/bridge"
MANIFEST = BRIDGE / "manifest.json"
BASE = f"https://raw.githubusercontent.com/buffedlizard55-lab/GEMSDOE/{UPSTREAM_COMMIT}/data/bridge/"


def download_data(out_dir: Path = ROOT / "data", *, base_url: str = BASE) -> list[dict]:
    """Verify every segment and concatenated file before replacing the canonical destination.

    Existing valid canonical files need no network. Local imported parts are preferred, then
    pinned upstream raw files. Transient/HTML/corrupt responses can never become training inputs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for entry in read_json(MANIFEST)["files"]:
        if Path(entry["canonical"]).name != entry["canonical"]:
            raise ValueError("Unsafe canonical filename in bridge manifest")
        dest = out_dir / entry["canonical"]
        if dest.exists() and dest.stat().st_size == entry["bytes"] and sha256(dest) == entry["sha256"]:
            receipts.append({"name": dest.name, "sha256": entry["sha256"], "bytes": entry["bytes"],
                             "method": "existing file rehashed"})
            print(f"Verified existing {dest.name}", flush=True)
            continue
        temporary = dest.with_name(dest.name + f".{os.getpid()}.part")
        full_hash = hashlib.sha256()
        try:
            with temporary.open("wb") as target:
                for piece in entry.get("parts", [entry]):
                    local = BRIDGE / piece["name"]
                    part_hash, size = hashlib.sha256(), 0
                    response = None
                    fetched = None
                    if Path(piece["name"]).name != piece["name"] or Path(entry["canonical"]).name != entry["canonical"]:
                        raise ValueError("Bridge filenames must not contain traversal or subdirectories")
                    if local.exists():
                        source = local.open("rb")
                        chunks = iter(lambda: source.read(1024 * 1024), b"")
                    else:
                        print(f"Downloading pinned {piece['name']}", flush=True)
                        try:
                            response = requests.get(base_url + piece["name"], stream=True, timeout=(15, 90))
                            response.raise_for_status()
                            source = None
                            chunks = response.iter_content(1024 * 1024)
                        except requests.RequestException as exc:
                            if response is not None:
                                response.close()
                            response = None
                            # Some sandboxes permit configured GitHub operations but block raw
                            # HTTPS. Use the same public pinned object, never disable TLS or ask
                            # for credentials. API raw media supports these <100 MB segments.
                            if base_url != BASE or shutil.which("gh") is None:
                                raise
                            print("Direct HTTPS unavailable; using configured GitHub CLI for the same pinned public object", flush=True)
                            fetched = tempfile.NamedTemporaryFile(dir=out_dir, suffix=".segment", delete=False)
                            try:
                                endpoint = f"repos/buffedlizard55-lab/GEMSDOE/contents/data/bridge/{piece['name']}?ref={UPSTREAM_COMMIT}"
                                result = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json", endpoint],
                                                        stdout=fetched, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                                        timeout=240, env={**os.environ, "GH_PROMPT_DISABLED": "true"})
                                fetched.close()
                                if result.returncode:
                                    raise RuntimeError("Configured GitHub data fallback failed: " + result.stderr.decode(errors="replace")[:600]) from exc
                                source = Path(fetched.name).open("rb")
                                chunks = iter(lambda: source.read(1024 * 1024), b"")
                            except Exception:
                                fetched.close()
                                Path(fetched.name).unlink(missing_ok=True)
                                raise
                    try:
                        for chunk in chunks:
                            if not chunk:
                                continue
                            size += len(chunk)
                            if size > piece["bytes"]:
                                raise ValueError(f"Oversized response for {piece['name']}")
                            part_hash.update(chunk)
                            full_hash.update(chunk)
                            target.write(chunk)
                    finally:
                        if source:
                            source.close()
                        if response is not None:
                            response.close()
                        if fetched is not None:
                            Path(fetched.name).unlink(missing_ok=True)
                    if size != piece["bytes"] or part_hash.hexdigest() != piece["sha256"]:
                        raise ValueError(f"Size/hash mismatch for {piece['name']}; canonical file untouched")
            if temporary.stat().st_size != entry["bytes"] or full_hash.hexdigest() != entry["sha256"]:
                raise ValueError(f"Concatenated hash mismatch for {dest.name}")
            temporary.replace(dest)
        finally:
            temporary.unlink(missing_ok=True)
        receipts.append({"name": dest.name, "sha256": entry["sha256"], "bytes": entry["bytes"],
                         "method": "pinned upstream bridge, segment and full hashes verified"})
    return receipts


def inspect_data(data_dir: Path = ROOT / "data") -> dict:
    pins = read_json(MANIFEST)
    files = []
    for entry in pins["files"]:
        path = data_dir / entry["canonical"]
        actual = sha256(path)
        if actual != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Input hash/size mismatch: {path}")
        files.append({"file": entry["canonical"], "bytes": path.stat().st_size, "sha256": actual,
                      "verification": "matches inherited mirror inventory; not an authenticated official hash"})
    valid, profile = template_info(data_dir / "sample_submission.tif")
    bands = []
    with rasterio.open(data_dir / "training_features.tif") as features:
        if (features.crs != profile["crs"] or features.transform != profile["transform"]
                or features.shape != valid.shape or features.count != 19):
            raise ValueError("Feature grid or 19-band count mismatch")
        union = np.zeros(valid.shape, dtype=bool)
        for band in range(1, features.count + 1):
            a = features.read(band, masked=True).filled(np.nan)
            a[a < -1e30] = np.nan
            good = np.isfinite(a)
            union |= good
            bands.append({"band": band, "name": features.tags(band).get("band_name", f"band_{band}"),
                          "embedded_description": features.descriptions[band - 1],
                          "valid_pixels": int(good.sum()),
                          "missing_inside_template": int((valid & ~good).sum()),
                          "metadata_status": "embedded metadata, not independent geological interpretation"})
    with rasterio.open(data_dir / "labels.tif") as lab:
        if lab.crs != profile["crs"] or lab.transform != profile["transform"] or lab.shape != valid.shape:
            raise ValueError("Label grid mismatch")
        y = lab.read(1)
        label_mask = lab.read_masks(1) != 0
        if not np.array_equal(valid, label_mask) or not np.isin(y[valid], [0, 1]).all():
            raise ValueError("Label footprint or binary codes disagree with reference")
    with rasterio.open(data_dir / "sample_submission.tif") as t:
        sample = t.read(1)
    return {"checked_at": utc_now(), "passed": True, "files": files,
            "source_commit": UPSTREAM_COMMIT,
            "width": profile["width"], "height": profile["height"], "crs": str(profile["crs"]),
            "transform": list(profile["transform"])[:6], "valid_pixels": int(valid.sum()),
            "outside_pixels": int((~valid).sum()), "known_fault_pixels": int((y[valid] == 1).sum()),
            "bands": bands, "feature_missing_inside_template": int((valid & ~union).sum()),
            "feature_present_outside_template": int((~valid & union).sum()),
            "template_positive_pixels": int((sample[valid] > 0).sum()),
            "irregularities": [
                {"id": "mirror-example-content", "severity": "review",
                 "finding": "Supplied template contains positive values; official page describes total absence.",
                 "resolution": "Only template grid and mask used. No template value is a prediction or feature.",
                 "source": "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format"},
                {"id": "footprint-difference", "severity": "handled",
                 "finding": "Feature validity differs from submission footprint.",
                 "resolution": "Predict every template-valid pixel; exporter refuses nonfinite outputs there."},
                {"id": "metadata-semantics", "severity": "review",
                 "finding": "Some embedded band descriptions (notably tc) may be interpretive/ambiguous.",
                 "resolution": "Retain band IDs and raw tags, do not assert geological meaning beyond official sources."}
            ]}


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["download", "inspect"])
    args = ap.parse_args()
    if args.command == "download":
        print(f"Free disk: {shutil.disk_usage(ROOT).free / 1e9:.1f} GB")
        download_data()
    report = inspect_data()
    write_json(ROOT / "evidence/data.json", report)
    print(f"PASS: {report['width']} x {report['height']}, {report['valid_pixels']:,} valid pixels")


if __name__ == "__main__":
    main()
