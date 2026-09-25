"""Publish only a real, fully validated artifact and independently pinned browser field/mask."""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import zipfile
import zlib
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from .common import MODEL_SOURCES, ROOT, read_json, sha256, utc_now, write_json
from .data import inspect_data
from .raster import template_info, validate_submission


def package_array(raw: bytes, path: Path, docs: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    compressed = zlib.compress(raw, level=9)
    if zlib.decompress(compressed) != raw:
        raise ValueError("Compression round trip failed")
    path.write_bytes(compressed)
    return {"file": path.relative_to(docs).as_posix(), "encoding": "zlib",
            "bytes": len(compressed), "sha256": hashlib.sha256(compressed).hexdigest(),
            "decoded_bytes": len(raw), "decoded_sha256": hashlib.sha256(raw).hexdigest()}


def build_preview(field: np.ndarray, valid: np.ndarray, destination: Path):
    """A measured model preview, not decorative/generated geographic imagery."""
    # Max pooling conserves visible narrow traces in a small preview; not used in the artifact.
    factor = 5
    h, w = field.shape
    hh, ww = (h + factor - 1) // factor, (w + factor - 1) // factor
    pad = np.zeros((hh * factor, ww * factor), dtype="float32")
    pad[:h, :w] = np.where(valid, field, 0)
    p = pad.reshape(hh, factor, ww, factor).max(axis=(1, 3))
    pad[:h, :w] = valid
    mask = pad.reshape(hh, factor, ww, factor).max(axis=(1, 3)) > 0
    rgb = np.zeros((hh, ww, 4), dtype="uint8")
    rgb[..., :3] = [24, 51, 49]
    rgb[..., 3] = mask * 255
    rgb[p > 0, :3] = np.stack([85 + 80 * p[p > 0], 168 + 70 * p[p > 0], 105 + 65 * p[p > 0]], axis=-1)
    Image.fromarray(rgb).save(destination)


def publish(report_path: Path, docs: Path = ROOT / "docs") -> dict:
    report = read_json(report_path)
    artifact = report["artifact"]
    name = artifact["filename"]
    if Path(name).name != name or not name.endswith(".tif"):
        raise ValueError("Unsafe artifact filename")
    source = report_path.parent / name
    if not source.is_file():
        source = docs / "downloads" / name
    if not source.is_file() or sha256(source) != artifact["sha256"]:
        raise ValueError("Experiment artifact missing or changed; no placeholder may be published")
    template = ROOT / "data/sample_submission.tif"
    if not template.exists():
        template = ROOT / "legacy/data/bridge/example_submission.tif"
    validation = validate_submission(source, template)
    if not validation["passed"]:
        raise ValueError("Candidate failed strict read-back validation")
    recorded_template = next(f["sha256"] for f in report["inputs"] if f["file"] == "sample_submission.tif")
    if sha256(template) != recorded_template:
        raise ValueError("Reference template differs from training provenance")
    valid, profile = template_info(template)
    with rasterio.open(source) as src:
        field = src.read(1).astype("<f4")
    field[~valid] = np.float32(np.nan)  # canonical little-endian quiet NaN for exact JS read-back
    support = float(np.mean(field[valid] > 0))
    if not report["config"]["min_emitted_fraction"] <= support <= report["config"]["max_emitted_fraction"]:
        raise ValueError("Artifact violates the experiment's support guard")
    if not np.isclose(support, report["deployment"]["published_support_fraction"], rtol=0, atol=1e-12):
        raise ValueError("Artifact support disagrees with the measured experiment record")
    legacy = ROOT / "legacy/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif"
    recorded_difference = report["artifact"]["new_pixel_field"]
    if sha256(legacy) != recorded_difference["legacy_sha256"]:
        raise ValueError("Legacy comparison artifact changed")
    with rasterio.open(legacy) as old:
        if old.shape != valid.shape or old.crs != profile["crs"] or old.transform != profile["transform"]:
            raise ValueError("Legacy comparison grid changed")
        difference = int(np.count_nonzero(old.read(1)[valid] != field[valid]))
    if difference == 0 or difference != recorded_difference["different_valid_pixels"]:
        raise ValueError("Reported legacy pixel difference does not match actual rasters")
    (docs / "data").mkdir(parents=True, exist_ok=True)
    (docs / "downloads").mkdir(parents=True, exist_ok=True)
    direct = docs / "downloads" / name
    if source.resolve() != direct.resolve():
        shutil.copyfile(source, direct)
    zip_path = direct.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        # Fixed metadata makes packaging deterministic across machines/runs.
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, direct.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != [name] or hashlib.sha256(archive.read(name)).hexdigest() != artifact["sha256"]:
            raise ValueError("ZIP must contain exactly the validated GeoTIFF")
    artifact_path = direct.relative_to(docs).as_posix()
    meta = {"schema_version": 1, "published_at": utc_now(), "candidate_id": artifact["sha256"][:10],
            "arm": report["selected"]["arm"], "note": artifact["note"],
            "competition_status": "unsubmitted; score unknown", "competition_score": None,
            "artifact": {"file": artifact_path, "filename": name, "sha256": sha256(direct),
                         "bytes": direct.stat().st_size},
            "zip": {"file": zip_path.relative_to(docs).as_posix(), "sha256": sha256(zip_path),
                    "bytes": zip_path.stat().st_size, "contains": [name]},
            "grid": {"width": profile["width"], "height": profile["height"], "epsg": 32611,
                     "res": [100, 100], "origin": [profile["transform"].c, profile["transform"].f],
                     "transform": list(profile["transform"])[:6],
                     "band_description": "Riftline fault confidence; not calibrated probability"},
            "valid_pixels": int(valid.sum()), "outside_pixels": int((~valid).sum()),
            "nonzero_pixels": int(np.count_nonzero(field[valid])),
            "field": package_array(field.tobytes(), docs / "data/field.f32.zlib", docs),
            "mask": package_array(np.packbits(valid.ravel(), bitorder="little").tobytes(),
                                  docs / "data/template-mask.bits.zlib", docs),
            "template_sha256": sha256(template), "validation": validation,
            "disclaimer": "Browser rebuilds precomputed model pixels, not model training. Its container hash can differ; pixel hash must match."}
    # Bind the adopted artifact to the exact executed source, not whatever code happens
    # to be current after review. A failed new training run never overwrites this bundle.
    bundle = report_path.parent / report.get("source_bundle", "source")
    if not bundle.is_dir():
        bundle = ROOT / "evidence/training-source"
    code_hash = hashlib.sha256()
    files = []
    for source_name in MODEL_SOURCES:
        source_file = bundle / source_name
        code_hash.update(source_name.encode())
        code_hash.update(source_file.read_bytes())
        files.append({"file": source_name, "sha256": sha256(source_file)})
    if code_hash.hexdigest() != report["code_sha256"] or sha256(bundle / "config.json") != report["config_sha256"]:
        raise ValueError("The candidate's executed code/config bundle cannot be verified")
    target_bundle = ROOT / "evidence/training-source"
    if bundle.resolve() != target_bundle.resolve():
        target_bundle.mkdir(parents=True, exist_ok=True)
        for name in [*MODEL_SOURCES, "config.json"]:
            shutil.copyfile(bundle / name, target_bundle / name)
    write_json(ROOT / "provenance/model-source.json", {"recorded_at": utc_now(),
               "bundle": "evidence/training-source", "code_sha256": code_hash.hexdigest(),
               "config_sha256": report["config_sha256"], "matches_executed_model_report": True, "files": files,
               "scope": "Exact executed source of the published candidate; not a retroactive current-code claim"})
    write_json(docs / "data/submission.json", meta)
    write_json(docs / "data/experiment.json", report)
    write_json(docs / "data/validation.json", validation)
    sources = read_json(ROOT / "research/sources.json")
    write_json(docs / "data/sources.json", sources)
    if (ROOT / "data/training_features.tif").is_file():
        data = inspect_data()
        write_json(ROOT / "evidence/data.json", data)
        write_json(docs / "data/data-inventory.json", data)
    elif (ROOT / "evidence/data.json").is_file():
        shutil.copyfile(ROOT / "evidence/data.json", docs / "data/data-inventory.json")
    with (docs / "data/source-catalog.csv").open("w", newline="", encoding="utf-8") as f:
        keys = ["id", "title", "publisher", "kind", "role", "access", "license", "used", "url"]
        writer = csv.DictWriter(f, keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sources["sources"])
    build_preview(field, valid, docs / "assets/prediction-preview.png")
    (docs / ".nojekyll").touch()
    print(f"Published {name}, {meta['artifact']['bytes']:,} bytes; all format gates passed")
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, default=ROOT / "outputs/riftline-v1/experiment.json")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs")
    args = ap.parse_args()
    publish(args.report, args.docs)


if __name__ == "__main__":
    main()
