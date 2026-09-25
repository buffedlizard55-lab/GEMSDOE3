import math

import numpy as np
import pytest

from gems3.metric import MetricContext
from legacy.src.metrics import GtContext, score_within_mask


def brute(p, truth, mask):
    gt = np.argwhere(truth)
    tp = 0.0
    for gy, gx in gt:
        if not mask[gy, gx]:
            continue
        values = [float(p[y, x]) * max(1 - math.hypot(y - gy, x - gx) / 3, 0)
                  for y in range(p.shape[0]) for x in range(p.shape[1])]
        tp += max(values)
    fp = 0.0
    for y, x in np.argwhere(mask):
        k = max((max(1 - math.hypot(y - gy, x - gx) / 3, 0) for gy, gx in gt), default=0)
        fp += float(p[y, x]) * (1 - k)
    fn = int(np.count_nonzero(truth & mask)) - tp
    return tp, fp, fn


@pytest.mark.parametrize("seed", list(range(6)))
def test_parity_with_brute_force_and_legacy(seed):
    rng = np.random.default_rng(seed)
    p = rng.uniform(size=(11, 12)).astype("float32")
    gt = rng.uniform(size=p.shape) > 0.85
    mask = rng.uniform(size=p.shape) > 0.35
    report = MetricContext(gt).score(p, mask)
    tp, fp, fn = brute(p, gt, mask)
    assert report["TP_w"] == pytest.approx(tp, abs=1e-7)
    assert report["FP_w"] == pytest.approx(fp, abs=2e-6)
    assert report["FN_w"] == pytest.approx(fn, abs=1e-7)
    legacy = score_within_mask(p, GtContext(gt), mask)
    assert report["dti"] == pytest.approx(legacy["dti"], abs=1e-7)


def test_perfect_missed_and_no_truth_cases():
    gt = np.zeros((15, 15), bool)
    gt[:, 7] = True
    ctx = MetricContext(gt)
    assert ctx.score(gt.astype("float32"))["dti"] == pytest.approx(1)
    assert ctx.score(np.zeros(gt.shape))["dti"] == 0
    no_truth = MetricContext(np.zeros(gt.shape, bool)).score(np.zeros(gt.shape))
    assert no_truth["dti"] is None


def test_boundary_uses_global_geometry():
    gt = np.zeros((10, 10), bool)
    gt[5, 4] = True
    mask = np.zeros_like(gt)
    mask[:, 5:] = True
    p = np.zeros(gt.shape, dtype="float32")
    p[5, 5] = 1
    report = MetricContext(gt).score(p, mask)
    assert report["FP_w"] == pytest.approx(1/3, abs=1e-7)
    assert report["dti"] is None  # no truth in that subregion; don't report a spurious perfect result


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -0.1, 1.1])
def test_metric_never_silently_repairs_predictions(bad):
    gt = np.eye(6, dtype=bool)
    p = np.zeros((6, 6), dtype="float32")
    p[2, 2] = bad
    with pytest.raises(ValueError):
        MetricContext(gt).score(p)


def test_partition_components_recompose():
    rng = np.random.default_rng(9)
    gt = rng.random((18, 19)) > 0.9
    p = rng.random(gt.shape).astype("float32")
    ctx = MetricContext(gt)
    mask = np.indices(gt.shape)[0] < 8
    left, right, all_ = ctx.score(p, mask), ctx.score(p, ~mask), ctx.score(p)
    for key in ["TP_w", "FP_w", "FN_w"]:
        assert left[key] + right[key] == pytest.approx(all_[key], abs=1e-6)
    assert all_["TP_w"] + all_["FN_w"] == np.count_nonzero(gt)
