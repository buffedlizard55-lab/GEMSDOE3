"""Publish the Coverline v3 portfolio: re-validate every file, pin hashes, archive the previous one.

The previous Gapfinder v2 manifest is preserved as docs/data/portfolio-gapfinder-v2.json and its
files stay downloadable, because the competition allows three uploads per week and the earlier
files are still valid candidates for the one final selection.
"""
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

PLAN = {
    "fusion": {"order": 1, "title": "Coverline fusion", "badge": "SUBMIT FIRST",
               "hypothesis": "Best expected score: model traces chosen by the metric-derived support "
                             "sweep, plus independently mapped USGS SGMC faults the labels omit.",
               "answers": "Does the coverage-selected field beat the previous session's files?"},
    "wide": {"order": 2, "title": "Coverline wide", "badge": "SUBMIT SECOND",
             "hypothesis": "The same arm at a deliberately larger support: more coverage, more false-"
                           "positive mass. The metric weights misses 4x more than false positives.",
             "answers": "wide minus fusion = whether the hidden labels reward more coverage than the "
                        "conservative operating point chooses."},
    "ml": {"order": 3, "title": "Coverline ML-only", "badge": "OPTIONAL THIRD",
           "hypothesis": "The selected model traces with no SGMC catalogue added.",
           "answers": "fusion minus ml = the measured leaderboard value of adding published SGMC "
                      "traces directly."},
}


POLICY_KEY = {"fusion": "selected", "ml": "selected", "wide": "wide"}
NOTE_MAX = 120  # our own brevity rule for the form's Note field; no official limit was verified


def compact_note(entry: dict, report: dict) -> str:
    """The paste-able Note: unique, traceable to the file hash, and short enough to read at a glance.

    The experiment record keeps the full descriptive note (`run_note` below). This compact form is
    what the manifest and the site show, because a Note is typed into a web form by a human.
    """
    variant = entry["variant"]
    policy = report[POLICY_KEY[variant]]
    arm = "Tversky-weighted classifier" if policy["arm"] == "tversky-weighted-classifier" else policy["arm"]
    suffix = {"fusion": "+ SGMC-gap traces", "ml": "no SGMC traces", "wide": "recall probe"}[variant]
    note = (f"Coverline v3 {variant} | {arm} | s={policy['support_target']:.2%} "
            f"h={policy['halo']} L={policy['tip']} | {suffix} | {entry['sha256'][:10]}")
    if len(note) > NOTE_MAX:
        raise ValueError(f"Note is {len(note)} characters; keep it under {NOTE_MAX}")
    return note


def preview(field: np.ndarray, valid: np.ndarray, sgmc: np.ndarray, dest: Path, factor: int = 5):
    h, w = field.shape
    hh, ww = (h + factor - 1) // factor, (w + factor - 1) // factor

    def pool(a):
        pad = np.zeros((hh * factor, ww * factor), dtype="float32")
        pad[:h, :w] = a
        return pad.reshape(hh, factor, ww, factor).max(axis=(1, 3)) > 0

    mask, model, published = pool(valid), pool(np.where(valid & ~sgmc, field, 0)), pool(sgmc & valid)
    rgba = np.zeros((hh, ww, 4), dtype="uint8")
    rgba[..., :3] = [24, 51, 49]
    rgba[..., 3] = mask * 255
    rgba[model] = [120, 220, 170, 255]
    rgba[published] = [245, 185, 80, 255]
    Image.fromarray(rgba).save(dest)


def publish(report_path: Path, docs: Path = ROOT / "docs") -> dict:
    report = read_json(report_path)
    run_dir = report_path.parent
    if report["strategy"] != "coverage-v3":
        raise ValueError("This publisher only accepts the frozen coverage-v3 experiment")
    template = ROOT / "data/sample_submission.tif"
    valid, _ = template_info(template)
    recorded = next(f["sha256"] for f in report["inputs"] if f["file"] == "sample_submission.tif")
    if sha256(template) != recorded:
        raise ValueError("Template differs from the experiment's recorded input")
    downloads = docs / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    for old in downloads.glob("coverage-v3-*"):
        old.unlink()  # only this publisher's own previous portfolio files
    items, fusion_field = [], None
    seen_sha = set()
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
        if entry["sha256"] in seen_sha:
            raise ValueError("Portfolio files must be distinct")
        seen_sha.add(entry["sha256"])
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
                      "sha256": entry["sha256"], "bytes": entry["bytes"], "note": compact_note(entry, report),
                      "run_note": entry["note"],
                      "emitted_pixels": entry["emitted_pixels"], "emitted_fraction": entry["emitted_fraction"],
                      "on_known_pixels": entry["on_known_pixels"], "different_pixels": entry["different_pixels"],
                      "checks_passed": sum(c["passed"] for c in check["checks"]),
                      "checks_total": len(check["checks"]), "validation": check,
                      "competition_score": None, "status": "unsubmitted; score unknown"})
    items.sort(key=lambda x: x["order"])
    if fusion_field is None:
        raise ValueError("The portfolio must contain a fusion file")
    with rasterio.open(ROOT / "legacy/data/evidence/proxy/proxy_catalogue.tif") as r:
        sgmc_gap = r.read(1) == 2
    preview(fusion_field, valid, sgmc_gap, docs / "assets/coverage-preview.png")
    current = docs / "data/portfolio.json"
    if current.exists():
        previous = read_json(current)
        if previous.get("strategy") != report["strategy"]:
            write_json(docs / "data/portfolio-gapfinder-v2.json", previous)
    manifest = {"schema_version": 1, "published_at": utc_now(), "strategy": report["strategy"],
                "experiment_completed_at": report["completed_at"], "selected": report["selected"],
                "wide": report["wide"], "deployment": report["deployment"],
                "metric_algebra": report["metric_algebra"], "items": items,
                "rule": "Three uploads per week; one final selection for both rounds (official rules §3.5, §3.6.2).",
                "disclaimer": "Format-validated locally. No file here has a known competition score."}
    write_json(current, manifest)
    slim = {k: v for k, v in report.items() if k != "candidates"}
    slim["candidates"] = [{k: c[k] for k in ("arm", "support_target", "floor", "halo", "tip", "eligible",
                                             "emitted_fraction", "robust_dti")}
                          | {"gap_dti": c["tuning"]["gap"]["dti"], "all_dti": c["tuning"]["all"]["dti"],
                             "known_dti": c["tuning"]["known"]["dti"]}
                          for c in report["candidates"]]
    write_json(docs / "data/coverage-experiment.json", slim)
    sources = read_json(ROOT / "research/sources.json")  # keep the published register in step
    write_json(docs / "data/sources.json", sources)
    with (docs / "data/source-catalog.csv").open("w", newline="", encoding="utf-8") as f:
        keys = ["id", "title", "publisher", "kind", "role", "access", "license", "used", "url"]
        writer = csv.DictWriter(f, keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sources["sources"])
    print(f"Published {len(items)} Coverline files; all strict format gates passed")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, default=ROOT / "outputs/coverage-v3/experiment.json")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs")
    args = ap.parse_args()
    publish(args.report, args.docs)


if __name__ == "__main__":
    main()
