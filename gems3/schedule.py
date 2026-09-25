"""Pindrop v4 emission layer: spend the pixel budget on a suppression-spaced node schedule.

Why this is not Coverline v3 with different numbers
---------------------------------------------------
Session 3 chose *how much* to emit from the official metric's algebra, but it emitted a dense,
one-pixel-wide oriented-ridge line: every pixel along a predicted trace carries p = 1. The metric's
own definitions, read literally, make most of that mass redundant:

* a truth pixel earns credit from the single best prediction within the 300 m (3 px) kernel, and
* a prediction pixel costs ``0.2 x (1 - k(d))`` in the denominator, where d is its distance to the
  nearest truth pixel.

Two predictions 4 pixels apart on the same trace cover almost exactly the same truth pixels, so the
second one buys (almost) nothing and still costs (almost) 0.2. The cheapest way to obey the metric is
therefore a **node schedule**: rank every candidate pixel by model confidence, then accept a pixel
only if no accepted pixel lies within a suppression square of half-width ``spacing - 1``. Along any
straight structure the surviving nodes are ``spacing`` pixels apart, so the largest distance from any
point of that structure to a node is ``spacing / 2``. With ``spacing = 5`` that is 2.5 px < 3 px: the
whole trace stays inside the kernel, while the emitted mass falls by up to 5x.

Falsifiable consequences, all measurable locally against the public catalogues:

1. at an identical emitted-pixel budget, the node schedule should cover at least as much truth as the
   dense ridge emission (higher TP_w) and add less false-positive weight (lower FP_w);
2. the measured ``credit per emitted pixel`` should rise with the spacing up to 5 and stop improving
   beyond it;
3. if it does not, the layer is wrong and the negative result is published.

Honesty constraints
-------------------
* The schedule is a *decision layer*: it never trains on, or looks at, proxy catalogues. Candidates
  come from the model field and the supplied-label geometry only.
* Tip-extension rays are constructed from the supplied traces; they are excluded from the held-out
  supplied-label proxy exactly as in gapfinder v2 / coverage v3, because they would otherwise collect
  kernel credit from the truth pixels that generated them.
* A sparse emission is a metric-aware encoding of a fault trace, not a calibrated probability and not
  a statement that faults are dotted in reality. The site says so, and the dense ridge control is
  published beside it so the choice can be tested on the leaderboard instead of assumed.
"""
from __future__ import annotations

import numpy as np

# The metric's triangular kernel reaches 300 m = 3 pixels at 100 m. Any point of a trace must stay
# strictly inside that radius of a node, so the largest integer spacing that cannot lose coverage at
# the midpoint is 5 (5 / 2 = 2.5 < 3).
KERNEL_RADIUS_PX = 3
MAX_SAFE_SPACING_PX = 2 * KERNEL_RADIUS_PX - 1


def spacing_covers_kernel(spacing: int, radius: int = KERNEL_RADIUS_PX) -> bool:
    """True when the midpoint between two nodes is still strictly inside the kernel radius."""
    if spacing < 1:
        raise ValueError("Spacing must be a positive integer")
    return spacing / 2.0 < radius


def candidate_pixels(field: np.ndarray, valid: np.ndarray, known: np.ndarray, ridges: np.ndarray,
                     dist_known: np.ndarray, halo: int, tip_rays: np.ndarray | None = None,
                     tip_ids: np.ndarray | None = None, tip_locations: np.ndarray | None = None
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Candidate pixels and their rank score.

    Candidates are oriented-ridge pixels inside the footprint, outside the supplied-label mask and
    outside the optional halo. When ``tip_rays`` is given, ray pixels become candidates too, ranked by
    the confidence of the tip that generated them (the ray is geometry-proposed and score-ranked, so
    it competes for the same budget as every other pixel instead of being added unconditionally).
    ``tip_ids`` holds the generating tip index per ray pixel and ``tip_locations`` the (n, 2) tip
    pixel coordinates, so a ray's rank is read from its parent tip's own confidence.
    """
    f = np.asarray(field, dtype="float32")
    v = np.asarray(valid, dtype=bool)
    k = np.asarray(known, dtype=bool)
    r = np.asarray(ridges, dtype=bool)
    if not (f.shape == v.shape == k.shape == r.shape):
        raise ValueError("Schedule inputs must share the full grid shape")
    if not np.isfinite(f).all() or np.any((f < 0) | (f > 1)):
        raise ValueError("Ranking requires finite [0,1] confidence")
    mask = r & v & ~k
    if halo:
        mask &= dist_known > halo
    score = np.where(mask, f, 0.0).astype("float32")
    if tip_rays is not None:
        rays = np.asarray(tip_rays, dtype=bool) & v & ~k
        if tip_ids is None or tip_locations is None:
            raise ValueError("Tip-ray candidates need their generating tip index and location")
        ids = np.asarray(tip_ids)
        locations = np.asarray(tip_locations, dtype="int64").reshape(-1, 2)
        if ids.shape != mask.shape:
            raise ValueError("Tip index grid must match the full grid shape")
        ray_only = rays & ~mask
        idx = np.flatnonzero(ray_only)
        if idx.size:
            parent = ids.ravel()[idx]
            if (parent < 0).any() or (parent >= len(locations)).any():
                raise ValueError("Every tip-ray pixel must record a valid generating tip")
            parent_rows, parent_cols = locations[parent, 0], locations[parent, 1]
            score.ravel()[idx] = f[parent_rows, parent_cols]
        mask = mask | rays
        score = np.where(mask, score, 0.0).astype("float32")
    return mask, score


def suppression_order(rows: np.ndarray, cols: np.ndarray, scores: np.ndarray, spacing: int) -> np.ndarray:
    """Order candidate indices greedily: best score first, suppressing a square of half-width spacing-1.

    ``spacing = 1`` suppresses nothing, which makes the node layer reduce exactly to a ranked prefix
    (a confidence floor) -- the dense ridge control. The returned indices follow the *acceptance*
    order, so any prefix of the result is itself a valid, nested emission set.
    """
    rows, cols, scores = np.asarray(rows), np.asarray(cols), np.asarray(scores, dtype="float64")
    if not (rows.shape == cols.shape == scores.shape):
        raise ValueError("Candidate arrays must be aligned")
    if rows.ndim != 1:
        raise ValueError("Candidates must be flat")
    if not np.isfinite(scores).all():
        raise ValueError("Candidate scores must be finite")
    if int(spacing) < 1:
        raise ValueError("Spacing must be a positive integer")
    order = np.argsort(-scores, kind="stable")
    if not len(order):
        return order
    top, bottom = int(rows.max()) + 1, int(cols.max()) + 1
    blocked = np.zeros((top, bottom), dtype=bool)
    half = int(spacing) - 1
    keep = np.empty(len(order), dtype=np.int64)
    accepted = 0
    for position in order:
        rr, cc = int(rows[position]), int(cols[position])
        if blocked[rr, cc]:
            continue
        keep[accepted] = position
        accepted += 1
        blocked[max(0, rr - half):rr + half + 1, max(0, cc - half):cc + half + 1] = True
    return keep[:accepted]


def budget_count(valid_pixels: int, fraction: float, available: int) -> int:
    """Node count for a budget expressed as a fraction of the valid footprint, capped by supply."""
    if valid_pixels <= 0:
        raise ValueError("No valid pixels")
    if not 0 < fraction <= 1:
        raise ValueError("Budget fraction must be inside (0, 1]")
    return int(min(max(1, round(fraction * valid_pixels)), int(available)))


def prefix_field(rows: np.ndarray, cols: np.ndarray, count: int, shape: tuple[int, int]) -> np.ndarray:
    """Binary float32 emission of the first `count` accepted nodes; zeros elsewhere."""
    out = np.zeros(shape, dtype="float32")
    n = int(count)
    if n < 0:
        raise ValueError("Cannot emit a negative number of nodes")
    if n:
        out[np.asarray(rows[:n], dtype="int64"), np.asarray(cols[:n], dtype="int64")] = 1.0
    return out


def pairwise_separation(rows: np.ndarray, cols: np.ndarray) -> dict:
    """Measured minimum Chebyshev and Euclidean separation of an emitted node set (diagnostic)."""
    from scipy.spatial import cKDTree

    rows, cols = np.asarray(rows, dtype="float64"), np.asarray(cols, dtype="float64")
    if rows.size < 2:
        return {"nodes": int(rows.size), "min_chebyshev": None, "min_euclidean": None,
                "min_euclidean_pair": None}
    pts = np.stack([rows, cols], axis=1)
    distances, indices = cKDTree(pts).query(pts, k=2)
    nearest = distances[:, 1]
    partner = indices[:, 1]
    arg = int(np.argmin(nearest))
    other = int(partner[arg])
    dx, dy = abs(rows[arg] - rows[other]), abs(cols[arg] - cols[other])
    return {"nodes": int(rows.size), "min_chebyshev": float(max(dx, dy)),
            "min_euclidean": float(nearest[arg]),
            "min_euclidean_pair": [[int(rows[arg]), int(cols[arg])], [int(rows[other]), int(cols[other])]]}
