"""Orientation-aware nonmaximum suppression, not catalogue copying or blanket dilation."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates


def ridge_mask(field: np.ndarray, valid: np.ndarray) -> np.ndarray:
    p = np.asarray(field, dtype="float32")
    if p.shape != valid.shape or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("Expected finite full-grid confidence and matching footprint")
    smooth = gaussian_filter(p, 1, mode="reflect")
    gy, gx = np.gradient(smooth)
    hyy, hyx = np.gradient(gy)
    hxy, hxx = np.gradient(gx)
    hxy = (hxy + hyx) / 2
    theta = 0.5 * np.arctan2(2 * hxy, hxx - hyy)
    # theta is the largest-eigenvalue axis; its orthogonal is the ridge normal.
    dx, dy = -np.sin(theta), np.cos(theta)
    eig_min = (hxx + hyy - np.sqrt((hxx - hyy) ** 2 + 4 * hxy ** 2)) / 2
    rr, cc = np.indices(p.shape, dtype="float32")
    plus = map_coordinates(smooth, [rr + dy, cc + dx], order=1, mode="nearest")
    minus = map_coordinates(smooth, [rr - dy, cc - dx], order=1, mode="nearest")
    # Strict on one side suppresses flat plateaux; minimum curvature excludes flat zeros.
    return valid & (eig_min < -1e-7) & (smooth > plus) & (smooth >= minus)


def emit(field: np.ndarray, valid: np.ndarray, floor: float, mode: str,
         ridges: np.ndarray | None = None) -> np.ndarray:
    if not 0 <= floor < 1 or mode not in {"soft-ridge", "binary-ridge"}:
        raise ValueError("Invalid emission policy")
    field, valid = np.asarray(field), np.asarray(valid, dtype=bool)
    if field.shape != valid.shape or field.ndim != 2 or not np.isfinite(field).all() or np.any((field < 0) | (field > 1)):
        raise ValueError("Emission requires finite [0,1] confidence and a matching 2-D mask")
    if ridges is not None and (np.asarray(ridges).shape != field.shape or np.asarray(ridges).dtype != bool):
        raise ValueError("Cached ridges must be a boolean mask on the same grid")
    ridges = ridge_mask(field, valid) if ridges is None else ridges
    keep = valid & ridges & (field >= floor)
    result = np.zeros(field.shape, dtype="float32")
    # Soft confidence retains ordering but is not claimed to be calibrated probability.
    result[keep] = np.clip(field[keep] / max(2 * floor, 0.25), 0, 1) if mode == "soft-ridge" else 1.0
    return result
