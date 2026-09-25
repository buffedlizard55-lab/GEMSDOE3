"""Publish the Gapfinder portfolio: re-validate every file, pin hashes, write web manifests."""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from .common import ROOT, read_json, sha256, utc_now, write_json
from .raster import template_info, validate_submission

# Recommended submission order and the question each upload answers on the public leaderboard.
PLAN = {
    "fusion": {"order": 1, "title": "Gapfinder fusion", "badge": "SUBMIT FIRST",
               "hypothesis": "Best expected score: model-predicted traces plus independently mapped USGS SGMC faults "
                             "that the supplied labels do not contain.",
               "answers": "Is the combined discovery field better than our earlier files?"},
    "ml": {"order": 2, "title": "Gapfinder ML-only", "badge": "SUBMIT SECOND",
           "hypothesis": "The same model traces with no SGMC traces added.",
           "answers": "fusion minus ml = the measured leaderboard value of adding SGMC traces directly."},
    "sgmc-gap": {"order": 3, "title": "SGMC-gap traces only", "badge": "OPTIONAL THIRD",
                 "hypothesis": "No model: only USGS SGMC faults more than 300 m from any supplied label.",
                 "answers": "How closely do the hidden expert faults follow published bedrock-fault maps?"},
}


def preview(field: np.ndarray, valid: np.ndarray, sgmc: np.ndarray, dest: Path, factor: int = 5):
    h, w = field.shape
    hh, ww = (h + factor - 1) // factor, (w + factor - 1) // factor

    def pool(a):
        pad = np.zeros((hh * factor, ww * factor), dtype="float32")
        pad[:h, :w] = a
        return pad.reshape(hh, factor, ww, factor).max(axis=(1, 3)) > 0
    m, ml, sg = pool(valid), pool(np.where(valid & ~sgmc, field, 0)), pool(sgmc & valid)
    rgba = np.zeros((hh, ww, 4), dtype="uint8")
    rgba[..., :3] = [24, 51, 49]
    rgba[..., 3] = m * 255
    rgba[ml] = [120, 220, 170, 255]
    rgba[sg] = [245, 185, 80, 255]
    Image.fromarray(rgba).save(dest)


def publish(report_path: Path, docs: Path = ROOT / "docs") -> dict:
    report = read_json(report_path)
    run_dir = report_path.parent
    template = ROOT / "data/sample_submission.tif"
    valid, _ = template_info(template)
    recorded = next(f["sha256"] for f in report["inputs"] if f["file"] == "sample_submission.tif")
    if sha256(template) != recorded:
        raise ValueError("Template differs from the experiment's recorded input")
    downloads = docs / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    for old in downloads.glob("gapfinder-*"):
        old.unlink()  # only this publisher's own previous portfolio files
    items = []
    fusion_field = None
    for entry in report["portfolio"]:
        name, zname = entry["file"], entry["zip"]
        for n in (name, zname):
            if Path(n).name != n:
                raise ValueError("Unsafe filename")
        src = run_dir / name
        if sha256(src) != entry["sha256"]:
            raise ValueError(f"{name} changed after the experiment")
        check = validate_submission(src, template)
        if not check["passed"]:
            raise ValueError(f"{name} failed strict validation")
        shutil.copyfile(src, downloads / name)
        shutil.copyfile(run_dir / zname, downloads / zname)
        with zipfile.ZipFile(downloads / zname) as z:
            if z.namelist() != [name] or hashlib.sha256(z.read(name)).hexdigest() != entry["sha256"]:
                raise ValueError("ZIP does not contain exactly the validated TIF")
        with rasterio.open(src) as r:
            field = r.read(1)
        inside = field[valid]
        if not (np.isfinite(inside).all() and inside.min() >= 0 and inside.max() <= 1):
            raise ValueError("Range check failed")
        if entry["variant"] == "fusion":
            fusion_field = np.where(valid, field, 0)
        plan = PLAN[entry["variant"]]
        items.append({**plan, "variant": entry["variant"], "file": f"downloads/{name}", "filename": name,
                      "zip": f"downloads/{zname}", "zip_sha256": sha256(downloads / zname),
                      "zip_bytes": (downloads / zname).stat().st_size,
                      "sha256": entry["sha256"], "bytes": entry["bytes"], "note": entry["note"],
                      "emitted_pixels": entry["emitted_pixels"], "emitted_fraction": entry["emitted_fraction"],
                      "on_known_pixels": entry["on_known_pixels"], "different_pixels": entry["different_pixels"],
                      "checks_passed": sum(c["passed"] for c in check["checks"]), "checks_total": len(check["checks"]),
                      "validation": check, "competition_score": None, "status": "unsubmitted; score unknown"})
    items.sort(key=lambda x: x["order"])
    with rasterio.open(ROOT / "legacy/data/evidence/proxy/proxy_catalogue.tif") as r:
        sgmc_gap = r.read(1) == 2
    preview(fusion_field, valid, sgmc_gap, docs / "assets/gapfinder-preview.png")
    manifest = {"schema_version": 1, "published_at": utc_now(), "strategy": report["strategy"],
                "experiment_completed_at": report["completed_at"], "selected": report["selected"],
                "deployment": report["deployment"], "items": items,
                "rule": "Three uploads per week; one final selection for both rounds (official rules §3.5, §3.6.2).",
                "disclaimer": "Format-validated locally. No file here has a known competition score."}
    write_json(docs / "data/portfolio.json", manifest)
    slim = {k: v for k, v in report.items() if k not in ("candidates",)}
    slim["candidates"] = [{k: c[k] for k in ("arm", "floor", "halo", "tip", "eligible", "emitted_fraction", "robust_dti")}
                          | {"gap_dti": c["tuning"]["gap"]["dti"], "all_dti": c["tuning"]["all"]["dti"],
                             "known_dti": c["tuning"].get("known", {}).get("dti")}
                          for c in report["candidates"]]
    write_json(docs / "data/gapfinder-experiment.json", slim)
    sources = read_json(ROOT / "research/sources.json")  # keep the published register in step
    write_json(docs / "data/sources.json", sources)
    with (docs / "data/source-catalog.csv").open("w", newline="", encoding="utf-8") as f:
        keys = ["id", "title", "publisher", "kind", "role", "access", "license", "used", "url"]
        writer = csv.DictWriter(f, keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sources["sources"])
    print(f"Published {len(items)} Gapfinder files; all strict format gates passed")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, default=ROOT / "outputs/gapfinder-v2/experiment.json")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs")
    a = ap.parse_args()
    publish(a.report, a.docs)


if __name__ == "__main__":
    main()
