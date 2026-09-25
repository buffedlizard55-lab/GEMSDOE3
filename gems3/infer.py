"""Apply a hash-verified trusted model to compatible features, without labels or retraining.

Joblib is an executable serialization format: only load a model whose trusted experiment
manifest you control. This is not a loader for arbitrary downloads. Confidence remains uncalibrated.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import rasterio

from .common import ROOT, read_json, sha256, write_json
from .emission import emit
from .features import build_features
from .raster import template_info, write_submission
from .train import predict_grid


def infer(features: Path, template: Path, model_path: Path, report_path: Path, out: Path,
          cache: Path = ROOT / "data/cache") -> dict:
    report = read_json(report_path)
    if sha256(model_path) != report["final_model_sha256"]:
        raise ValueError("Model does not match trusted experiment hash; refusing deserialization")
    valid, profile = template_info(template)
    with rasterio.open(features) as src:
        if src.count != 19 or src.shape != valid.shape or src.crs != profile["crs"] or src.transform != profile["transform"]:
            raise ValueError("Inference feature count/grid must match the reference exactly")
        names = [src.tags(i).get("band_name", f"band_{i}") for i in range(1, 20)]
        if names != report["features"]["names"][:19]:
            raise ValueError("Inference band identities/order differ from training")
    matrix, ids, feature_meta = build_features(features, valid, cache, report["config"])
    arm = next(a for a in report["config"]["arms"] if a["id"] == report["selected"]["arm"])
    model = joblib.load(model_path)
    expected = matrix.shape[1] if arm["context"] else 19
    if getattr(model, "n_features_in_", None) != expected:
        raise ValueError("Model feature count differs from recipe")
    raw, clipped = predict_grid(model, matrix, ids, valid.shape, arm)
    field = emit(raw, valid, report["selected"]["floor"], report["selected"]["emission"])
    support = float(np.mean(field[valid] > 0))
    config = report["config"]
    if not config["min_emitted_fraction"] <= support <= config["max_emitted_fraction"]:
        raise ValueError("Inference violates frozen support policy; no automatic threshold retuning")
    validation = write_submission(field, template, out, tags={"source": "Riftline frozen-model inference",
                                  "model_sha256": report["final_model_sha256"]})
    receipt = {"model_sha256": report["final_model_sha256"], "features_sha256": sha256(features),
               "template_sha256": sha256(template), "feature_metadata": feature_meta,
               "model_bounded_link_clipped_pixels": clipped, "support_fraction": support,
               "labels_used": False, "validation": validation,
               "pixel_field_sha256": sha256_pixel_field(field, valid),
               "competition_score": None}
    write_json(out.with_suffix(".receipt.json"), receipt)
    return receipt


def sha256_pixel_field(field, valid):
    import hashlib
    pixels = field.astype("<f4", copy=True)
    pixels[~valid] = np.nan
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path, default=ROOT / "data/training_features.tif")
    ap.add_argument("--template", type=Path, default=ROOT / "data/sample_submission.tif")
    ap.add_argument("--model", type=Path, default=ROOT / "outputs/riftline-v1/final-model.joblib")
    ap.add_argument("--report", type=Path, default=ROOT / "outputs/riftline-v1/experiment.json")
    ap.add_argument("--output", type=Path, default=ROOT / "outputs/frozen-inference.tif")
    args = ap.parse_args()
    receipt = infer(args.features, args.template, args.model, args.report, args.output)
    print(f"PASS: {args.output}; source labels not used; {receipt['pixel_field_sha256']}")


if __name__ == "__main__":
    main()
