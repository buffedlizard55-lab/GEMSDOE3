"""Regression tests for the Pindrop v4 emission layer.

The central falsifiable claim is metric-level, so it is tested against the project's own
implementation of the official metric: at an identical emitted-pixel budget, a suppression-spaced
node schedule must cover at least as much truth as the dense ridge line while adding no more
false-positive weight.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.ndimage import distance_transform_edt

from gems3.metric import MetricContext
from gems3.schedule import (
    MAX_SAFE_SPACING_PX,
    budget_count,
    candidate_pixels,
    pairwise_separation,
    prefix_field,
    spacing_covers_kernel,
    suppression_order,
)


def line_grid(rows=3, cols=61):
    valid = np.ones((rows, cols), dtype=bool)
    known = np.zeros_like(valid)
    field = np.zeros((rows, cols), dtype="float32")
    field[1, :] = 1.0
    ridges = np.zeros_like(valid)
    ridges[1, :] = True
    dist_known = distance_transform_edt(~known).astype("float32")
    return valid, known, field, ridges, dist_known


def test_safe_spacing_is_the_kernel_nyquist_limit():
    assert MAX_SAFE_SPACING_PX == 5
    assert spacing_covers_kernel(5) and spacing_covers_kernel(4) and spacing_covers_kernel(1)
    assert not spacing_covers_kernel(6) and not spacing_covers_kernel(7)
    with pytest.raises(ValueError):
        spacing_covers_kernel(0)


def test_spacing_one_reduces_to_a_ranked_prefix():
    valid, known, field, ridges, dist_known = line_grid()
    rng = np.random.default_rng(0)
    field = rng.random(field.shape).astype("float32")
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0)
    rows, cols = np.nonzero(mask)
    order = suppression_order(rows, cols, score[rows, cols], 1)
    expected = np.argsort(-score[rows, cols], kind="stable")
    assert np.array_equal(order, expected)


def test_nodes_respect_the_documented_separation():
    valid, known, _, _, dist_known = line_grid(rows=41, cols=41)
    rng = np.random.default_rng(1)
    field = rng.random(valid.shape).astype("float32")
    ridges = np.ones_like(valid)
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0)
    rows, cols = np.nonzero(mask)
    for spacing in (4, 5):
        order = suppression_order(rows, cols, score[rows, cols], spacing)
        measured = pairwise_separation(rows[order], cols[order])
        assert measured["min_chebyshev"] >= spacing
        assert measured["min_euclidean"] >= spacing


def test_a_straight_trace_stays_inside_the_kernel_at_spacing_five():
    """Every pixel of a covered trace must remain within the 300 m kernel of an emitted node."""
    valid, known, field, ridges, dist_known = line_grid()
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0)
    rows, cols = np.nonzero(mask)
    order = suppression_order(rows, cols, score[rows, cols], 5)
    emitted = prefix_field(rows[order], cols[order], len(order), valid.shape).astype(bool)
    distance = distance_transform_edt(~emitted)
    assert distance[1, :].max() <= 5 / 2  # midpoint of the schedule gap
    assert distance[1, :].max() < 3       # strictly inside the metric kernel


def test_same_budget_sparse_covers_more_truth_than_dense():
    """The mechanism claim, measured with the official metric implementation on synthetic truth.

    Both emissions spend exactly 25 pixels. The dense line covers 25 pixels of a 251-pixel trace; the
    spaced schedule covers 125, because each node still covers 5 trace pixels inside the kernel.
    """
    valid, known, field, ridges, dist_known = line_grid(cols=251)
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0)
    rows, cols = np.nonzero(mask)
    assert len(rows) > 200
    dense = prefix_field(rows, cols, 25, valid.shape)
    order = suppression_order(rows, cols, score[rows, cols], 5)
    sparse = prefix_field(rows[order], cols[order], 25, valid.shape)
    truth = np.zeros(valid.shape, dtype="int8")
    truth[1, :] = 1
    ctx = MetricContext(truth)
    dense_score, sparse_score = ctx.score(dense, valid), ctx.score(sparse, valid)
    assert dense.sum() == sparse.sum() == 25
    assert sparse_score["TP_w"] > dense_score["TP_w"]
    assert sparse_score["FN_w"] < dense_score["FN_w"]
    assert sparse_score["FP_w"] <= dense_score["FP_w"]
    assert sparse_score["dti"] > dense_score["dti"]


def test_candidate_mask_excludes_known_halo_and_outside():
    valid = np.ones((7, 7), dtype=bool)
    valid[0, :] = False
    known = np.zeros_like(valid)
    known[3, 3] = True
    ridges = np.zeros_like(valid)
    ridges[2, :] = True
    field = np.ones((7, 7), dtype="float32")
    dist_known = distance_transform_edt(~known).astype("float32")
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0)
    assert not mask[0, :].any()          # outside the footprint
    assert not mask[3, 3].any()          # supplied label
    mask_halo, _ = candidate_pixels(field, valid, known, ridges, dist_known, halo=2)
    assert mask_halo.sum() < mask.sum()  # halo removes near-label candidates
    assert np.isfinite(score).all() and score.max() <= 1


def test_tip_rays_are_ranked_by_their_parent_tip():
    valid = np.ones((5, 9), dtype=bool)
    known = np.zeros_like(valid)
    ridges = np.zeros_like(valid)
    ridges[2, 3] = True
    ridges[2, 5] = True
    field = np.zeros((5, 9), dtype="float32")
    field[2, 3], field[2, 5] = 0.9, 0.2
    ids = np.full(valid.shape, -1, dtype="int64")
    ids[2, 4] = 0    # a ray pixel generated by the high-confidence tip
    ids[2, 6] = 1    # a ray pixel generated by the low-confidence tip
    locations = np.array([[2, 3], [2, 5]], dtype="int64")
    dist_known = np.ones(valid.shape, dtype="float32")
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, halo=0,
                                   tip_rays=ids >= 0, tip_ids=ids, tip_locations=locations)
    assert mask[2, 4] and mask[2, 6]
    assert score[2, 4] == pytest.approx(0.9)
    assert score[2, 6] == pytest.approx(0.2)


def test_tip_rays_need_parent_indices():
    valid, known, field, ridges, dist_known = line_grid()
    with pytest.raises(ValueError):
        candidate_pixels(field, valid, known, ridges, dist_known, halo=0,
                         tip_rays=np.ones_like(valid))


def test_tip_rays_reject_an_out_of_range_parent():
    valid, known, field, ridges, dist_known = line_grid()
    ids = np.full(valid.shape, -1, dtype="int64")
    ids[2, 1] = 4  # a non-ridge ray pixel whose parent index does not exist
    with pytest.raises(ValueError):
        candidate_pixels(field, valid, known, ridges, dist_known, halo=0,
                         tip_rays=ids >= 0, tip_ids=ids,
                         tip_locations=np.array([[1, 2]], dtype="int64"))


def test_candidate_pixels_reject_invalid_confidence():
    valid, known, field, ridges, dist_known = line_grid()
    bad = field.copy()
    bad[1, 1] = np.nan
    with pytest.raises(ValueError):
        candidate_pixels(bad, valid, known, ridges, dist_known, halo=0)


def test_budget_count_is_capped_by_supply_and_positive():
    assert budget_count(1000, 0.01, 500) == 10
    assert budget_count(1000, 0.5, 500) == 500
    assert budget_count(1000, 0.0001, 500) == 1
    with pytest.raises(ValueError):
        budget_count(0, 0.01, 10)
    with pytest.raises(ValueError):
        budget_count(1000, 0.0, 10)


def test_prefix_field_is_nested_and_binary():
    rows = np.array([0, 1, 2, 3, 4], dtype="int64")
    cols = np.array([0, 0, 0, 0, 0], dtype="int64")
    small = prefix_field(rows, cols, 2, (6, 6))
    large = prefix_field(rows, cols, 5, (6, 6))
    assert small.sum() == 2 and large.sum() == 5
    assert np.all(large[small > 0] == 1)
    assert set(np.unique(large)) <= {0.0, 1.0}
    with pytest.raises(ValueError):
        prefix_field(rows, cols, -1, (6, 6))


def test_pairwise_separation_measures_the_closest_pair():
    rows = np.array([0, 0, 5], dtype="int64")
    cols = np.array([0, 3, 0], dtype="int64")
    measured = pairwise_separation(rows, cols)
    assert measured["nodes"] == 3
    assert measured["min_euclidean"] == pytest.approx(3.0)
    assert measured["min_chebyshev"] == pytest.approx(3.0)
    assert pairwise_separation(rows[:1], cols[:1])["min_euclidean"] is None


def test_suppression_order_rejects_invalid_input():
    rows = np.array([0, 1], dtype="int64")
    with pytest.raises(ValueError):
        suppression_order(rows, rows, np.array([1.0]), 5)
    with pytest.raises(ValueError):
        suppression_order(rows, rows, np.array([1.0, np.nan]), 5)
    with pytest.raises(ValueError):
        suppression_order(rows, rows, np.array([1.0, 0.5]), 0)
