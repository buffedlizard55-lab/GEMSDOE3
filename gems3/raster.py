"""Fail-closed GeoTIFF submission IO. The template MASK, not features, defines the footprint.

Spec: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format
A passed local check proves the documented format, NOT acceptance or accuracy on DrivenData.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from .common import sha256, utc_now


def template_info(path: str | Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        if (src.count != 1 or src.dtypes != ("float32",) or src.crs is None
                or src.crs.to_epsg() != 32611 or src.res != (100.0, 100.0)
                or src.transform.b != 0 or src.transform.d != 0
                or src.transform.a != 100 or src.transform.e != -100
                or src.tags().get("AREA_OR_POINT", "Area") != "Area"):
            raise ValueError("Template must be one float32 band, north-up 100 m EPSG:32611, pixel-is-area")
        raw = src.read(1)
        valid = np.isfinite(raw) & (src.read_masks(1) != 0)
        if not valid.any():
            raise ValueError("Template has no valid pixels")
        if np.isinf(raw).any() or np.any((raw[valid] < 0) | (raw[valid] > 1)):
            raise ValueError("Template has invalid reference values")
        profile = src.profile.copy()
    return valid, profile


def validate_submission(path: str | Path, template: str | Path) -> dict:
    """Read every pixel in bounded windows and return measured gates, never a warning-only pass."""
    path, template = Path(path), Path(template)
    checks: list[dict] = []

    def check(name: str, condition: bool, detail: object):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    counts = {"valid_pixels": 0, "outside_pixels": 0, "invalid_inside": 0,
              "out_of_range": 0, "non_nan_outside": 0, "mask_mismatches": 0,
              "nonzero_pixels": 0}
    minimum, maximum = float("inf"), float("-inf")
    grid = None
    try:
        # Validate the reference itself before allowing it to authorize any candidate.
        _, reference = template_info(template)
        with rasterio.open(template) as ref, rasterio.open(path) as pred:
            grid = {"width": pred.width, "height": pred.height,
                    "crs": str(pred.crs), "transform": list(pred.transform)[:6],
                    "dtype": pred.dtypes[0], "bands": pred.count,
                    "resolution_m": list(pred.res)}
            check("GeoTIFF driver", pred.driver == "GTiff", pred.driver)
            check("one band", pred.count == 1, pred.count)
            check("float32", pred.dtypes == ("float32",), list(pred.dtypes))
            same_shape = pred.shape == ref.shape
            check("template shape", same_shape, [list(pred.shape), list(ref.shape)])
            check("template CRS / EPSG:32611", pred.crs == ref.crs, str(pred.crs))
            check("exact affine transform", pred.transform == ref.transform, list(pred.transform)[:6])
            check("NaN nodata", pred.nodata is not None and bool(np.isnan(pred.nodata)),
                  "nan" if pred.nodata is not None and np.isnan(pred.nodata) else str(pred.nodata))
            check("pixel-is-area", pred.tags().get("AREA_OR_POINT", "Area") == "Area",
                  pred.tags().get("AREA_OR_POINT", "Area"))
            if same_shape and pred.count == 1:
                for row in range(0, ref.height, 256):
                    window = Window(0, row, ref.width, min(256, ref.height - row))
                    t = ref.read(1, window=window)
                    valid = np.isfinite(t) & (ref.read_masks(1, window=window) != 0)
                    arr = pred.read(1, window=window)
                    inside = arr[valid]
                    finite = inside[np.isfinite(inside)]
                    counts["valid_pixels"] += int(valid.sum())
                    counts["outside_pixels"] += int((~valid).sum())
                    counts["invalid_inside"] += int((~np.isfinite(inside)).sum())
                    counts["out_of_range"] += int(((finite < 0) | (finite > 1)).sum())
                    counts["non_nan_outside"] += int((~np.isnan(arr[~valid])).sum())
                    counts["mask_mismatches"] += int(((pred.read_masks(1, window=window) != 0) != valid).sum())
                    counts["nonzero_pixels"] += int((finite > 0).sum())
                    if finite.size:
                        minimum, maximum = min(minimum, float(finite.min())), max(maximum, float(finite.max()))
                check("finite inside template mask", counts["invalid_inside"] == 0, counts["invalid_inside"])
                check("inside values in [0,1]", counts["out_of_range"] == 0, counts["out_of_range"])
                check("NaN outside template mask", counts["non_nan_outside"] == 0, counts["non_nan_outside"])
                check("no hidden mask disagreement", counts["mask_mismatches"] == 0, counts["mask_mismatches"])
            check("valid reference", reference["width"] > 0, sha256(template))
    except (OSError, ValueError, rasterio.errors.RasterioError) as exc:
        check("readable candidate and reference", False, str(exc))
    passed = bool(checks) and all(c["passed"] for c in checks)
    return {"schema_version": 1, "checked_at": utc_now(), "passed": passed,
            "meaning": "Local documented-format validation only; no platform acceptance or score implied.",
            "file": path.name, "sha256": sha256(path) if path.is_file() else None,
            "bytes": path.stat().st_size if path.is_file() else None,
            "template_sha256": sha256(template) if template.is_file() else None,
            "grid": grid, "checks": checks, "counts": counts,
            "min": minimum if np.isfinite(minimum) else None,
            "max": maximum if np.isfinite(maximum) else None}


def write_submission(field: np.ndarray, template: str | Path, path: str | Path, *, tags=None,
                     description: str = "Riftline fault confidence; not calibrated probability") -> dict:
    """No silent clipping or NaN filling. Only outside-footprint masking is automatic."""
    valid, profile = template_info(template)
    arr = np.asarray(field)
    if arr.shape != valid.shape:
        raise ValueError(f"Prediction shape {arr.shape} != template {valid.shape}")
    if np.ma.isMaskedArray(field) and np.any(np.ma.getmaskarray(field) & valid):
        raise ValueError("Masked prediction inside template; publication refused")
    inside = arr[valid]
    if not np.isfinite(inside).all():
        raise ValueError("Nonfinite prediction inside template; publication refused")
    if np.any((inside < 0) | (inside > 1)):
        raise ValueError("Prediction outside [0,1]; publication refused, not silently clipped")
    out = arr.astype("float32", copy=True)
    out[~valid] = np.nan
    profile.update(driver="GTiff", count=1, dtype="float32", nodata=float("nan"),
                   compress="deflate", predictor=3, tiled=True, blockxsize=256, blockysize=256)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + f".{os.getpid()}.pending.tif")
    try:
        with rasterio.open(tmp, "w", **profile) as dst:
            dst.write(out, 1)
            dst.set_band_description(1, description)
            dst.update_tags(AREA_OR_POINT="Area", **(tags or {}))
        report = validate_submission(tmp, template)
        if not report["passed"]:
            raise ValueError(f"Written file failed independent read-back: {report['checks']}")
        tmp.replace(path)
        report["file"] = path.name
        return report
    finally:
        tmp.unlink(missing_ok=True)
