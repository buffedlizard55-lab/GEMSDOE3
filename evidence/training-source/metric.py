"""Distance-weighted Tversky from the official equations, alpha=.2 beta=.8 R=3 px.

https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric
No thresholding probabilities. Maximum p*k near each truth pixel (not average convolution).
Unlike the inherited scorer, invalid probabilities are rejected rather than quietly sanitized.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import distance_transform_edt


class MetricContext:
    def __init__(self, truth: np.ndarray, radius: int = 3):
        self.truth = np.asarray(truth, dtype=bool)
        if self.truth.ndim != 2 or not isinstance(radius, int) or radius <= 0:
            raise ValueError("Need 2-D truth and a positive integer radius")
        self.radius = radius
        self.rows, self.cols = np.nonzero(self.truth)
        self.fp_weight = (np.minimum(distance_transform_edt(~self.truth) / radius, 1).astype("float32")
                          if self.rows.size else np.ones(self.truth.shape, dtype="float32"))
        self.offsets = [(dy, dx, 1 - math.hypot(dy, dx) / radius)
                        for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)
                        if math.hypot(dy, dx) < radius]

    def score(self, prediction: np.ndarray, mask: np.ndarray | None = None) -> dict:
        p = np.asarray(prediction)
        if p.shape != self.truth.shape or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
            raise ValueError("Metric expects finite [0,1] full-grid predictions (0 outside)")
        m = np.ones(p.shape, bool) if mask is None else np.asarray(mask, bool)
        if m.shape != p.shape:
            raise ValueError("Scoring-mask shape mismatch")
        select = m[self.rows, self.cols]
        rows, cols = self.rows[select], self.cols[select]
        credit = np.zeros(rows.size, dtype="float64")
        h, w = p.shape
        for dy, dx, k in self.offsets:
            rr, cc = rows + dy, cols + dx
            good = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            credit[good] = np.maximum(credit[good], p[rr[good], cc[good]].astype("float64") * k)
        tp = float(credit.sum())
        fn = float(rows.size) - tp
        active = m & (p > 0)
        fp = float(np.sum(p[active].astype("float64") * self.fp_weight[active], dtype="float64"))
        # A no-truth diagnostic region is reported as unavailable, not a flattering 1.0.
        dti = tp / (tp + 0.2 * fp + 0.8 * fn + 1e-7) if rows.size else None
        return {"dti": dti, "TP_w": tp, "FP_w": fp, "FN_w": fn, "truth_pixels": int(rows.size),
                "prediction_pixels": int(active.sum()), "prediction_mass": float(p[m].sum(dtype="float64")),
                "scored_pixels": int(m.sum()), "meaning": "published-catalogue surrogate, not a competition score"}
