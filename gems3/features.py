"""Label-free multiscale geophysical context on the competition grid; bounded-memory cache."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter

from .common import read_json, sha256, write_json

FEATURE_VERSION = 1


def spatial_partition(shape: tuple[int, int], block_px: int = 512, buffer_px: int = 32,
                      origin: tuple[int, int] = (0, 0)):
    """Deterministic label-independent four-way spatial split, with eroded block interiors.

    `origin` shifts every block boundary by that many pixels, which rotates the partition without
    changing its block size. Rotating is the only honest way to obtain a second look at the same
    survey footprint: the blocks are new but the underlying region necessarily overlaps. Callers
    that rotate must disclose the overlap instead of calling the result independent.
    """
    if block_px <= 2 * buffer_px + 3 or buffer_px < 3:
        raise ValueError("Blocks need nonempty interiors and at least the 3 px metric buffer")
    oy, ox = int(origin[0]), int(origin[1])
    if not 0 <= oy < block_px or not 0 <= ox < block_px:
        raise ValueError("Block origin must fall inside one block period")
    rr, cc = np.indices(shape, dtype="int64")
    sr, sc = rr + oy, cc + ox
    folds = ((sr // block_px) * 3 + (sc // block_px) * 5) % 4
    inside = ((sr % block_px >= buffer_px) & (sr % block_px < block_px - buffer_px)
              & (sc % block_px >= buffer_px) & (sc % block_px < block_px - buffer_px)
              & (rr < shape[0] - buffer_px) & (cc < shape[1] - buffer_px))
    return folds.astype("uint8"), inside


def normalized_smooth(a: np.ndarray, sigma: float) -> np.ndarray:
    """Mask-aware Gaussian; nodata can never act as an extreme physical measurement."""
    good = np.isfinite(a)
    numerator = gaussian_filter(np.where(good, a, 0).astype("float32"), sigma, mode="reflect", truncate=4)
    denominator = gaussian_filter(good.astype("float32"), sigma, mode="reflect", truncate=4)
    result = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 1e-6)
    result[denominator <= 1e-6] = np.nan
    return result


def context_planes(a: np.ndarray, scale: float):
    """Local relief, edge magnitude, signed curvature and direction-free curvature anisotropy."""
    smooth = normalized_smooth(a, scale)
    gy, gx = np.gradient(smooth)
    hyy, hyx = np.gradient(gy)
    hxy, hxx = np.gradient(gx)
    hxy = (hxy + hyx) * 0.5
    delta = np.sqrt((hxx - hyy) ** 2 + 4 * hxy ** 2)
    anisotropy = delta / (np.abs(hxx + hyy) + delta + 1e-6)
    return {"relief": a - smooth, "gradient": np.hypot(gx, gy),
            "curvature": hxx + hyy, "anisotropy": anisotropy}


def build_features(features_path: Path, valid: np.ndarray, cache_dir: Path, config: dict):
    """Store only template-valid rows; no labels, coordinates, or proxy values in the features.

    Operators use at most 4*max(sigma)+2 pixels of context. Cache reuse requires hashes of
    input raster, footprint, code version, band list and scales. Never reuse a partial cache.
    """
    config_key = {"version": FEATURE_VERSION, "implementation_sha256": sha256(Path(__file__)),
                  "raster": sha256(features_path),
                  "valid": hashlib.sha256(valid.tobytes()).hexdigest(),
                  "bands": config["derived_bands"], "scales": config["scales_px"]}
    if config["buffer_px"] < 4 * max(config["scales_px"]) + 2:
        raise ValueError("Spatial buffer is smaller than the feature-context support")
    key = hashlib.sha256(json.dumps(config_key, sort_keys=True).encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path, meta_path = cache_dir / f"features-{key[:16]}.npy", cache_dir / f"features-{key[:16]}.json"
    ids = np.flatnonzero(valid)
    if path.exists() and meta_path.exists():
        meta = read_json(meta_path)
        if meta["key"] == key and sha256(path) == meta["file_sha256"]:
            print("Reusing verified label-free feature cache", flush=True)
            return np.load(path, mmap_mode="r"), ids, meta
    names = []
    with rasterio.open(features_path) as src:
        if src.shape != valid.shape:
            raise ValueError("Feature/footprint shape mismatch")
        n_columns = src.count + len(config["derived_bands"]) * len(config["scales_px"]) * 4
        temporary = path.with_suffix(".pending.npy")
        matrix = np.lib.format.open_memmap(temporary, mode="w+", dtype="float32",
                                          shape=(len(ids), n_columns))
        try:
            for band in range(1, src.count + 1):
                a = src.read(band, masked=True).filled(np.nan)
                a[a < -1e30] = np.nan
                names.append(src.tags(band).get("band_name", f"band_{band}"))
                matrix[:, band - 1] = a.ravel()[ids]
            col = src.count
            for band in config["derived_bands"]:
                a = src.read(band, masked=True).filled(np.nan)
                a[a < -1e30] = np.nan
                for scale in config["scales_px"]:
                    print(f"Context band {band}, sigma={scale} px", flush=True)
                    for operator, plane in context_planes(a, scale).items():
                        matrix[:, col] = plane.ravel()[ids]
                        names.append(f"b{band}_s{scale}_{operator}")
                        col += 1
            matrix.flush()
            del matrix
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    meta = {"key": key, "config": config_key, "shape": [len(ids), len(names)],
            "names": names, "file_sha256": sha256(path), "max_context_radius_px": 4 * max(config["scales_px"]) + 2,
            "labels_used": False, "coordinates_used": False, "proxy_used": False}
    write_json(meta_path, meta)
    return np.load(path, mmap_mode="r"), ids, meta
