import numpy as np
import pytest

from gems3.emission import emit, ridge_mask
from gems3.features import context_planes, normalized_smooth, spatial_partition
from gems3.train import choose_candidate, fit_arm, sample_rows


def test_spatial_masks_disjoint_with_real_exclusion_buffer():
    folds, interior = spatial_partition((181, 199), 64, 8)
    train = interior & np.isin(folds, [2, 3])
    tune, audit = interior & (folds == 0), interior & (folds == 1)
    assert not np.any(train & (tune | audit)) and not np.any(tune & audit)
    assert all(np.any(m) for m in [train, tune, audit])
    assert not interior[:8].any() and not interior[-8:].any()
    assert not interior[:, 56:72].any()
    assert np.array_equal(folds, spatial_partition((181, 199), 64, 8)[0])


def test_buffer_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        spatial_partition((100, 100), 64, 33)
    with pytest.raises(ValueError):
        spatial_partition((100, 100), 64, 0)


def test_normalized_smoothing_ignores_missing_footprint():
    a = np.ones((30, 30), dtype="float32") * 7
    a[:5] = np.nan
    smoothed = normalized_smooth(a, 3)
    np.testing.assert_allclose(smoothed[np.isfinite(smoothed)], 7, atol=1e-5)
    planes = context_planes(a, 3)
    assert len(planes) == 4
    assert np.nanmax(np.abs(planes["gradient"])) < 1e-5
    assert np.nanmax(np.abs(planes["curvature"])) < 1e-5


def test_no_context_is_fabricated_in_entirely_missing_data():
    a = np.full((25, 25), np.nan, dtype="float32")
    assert np.isnan(normalized_smooth(a, 1)).all()


@pytest.mark.parametrize("vertical", [False, True])
def test_ridge_normal_recovers_thin_center(vertical):
    y, x = np.indices((41, 41))
    field = np.exp(-(((x if vertical else y) - 20) ** 2) / 10).astype("float32")
    valid = np.ones(field.shape, bool)
    mask = ridge_mask(field, valid)
    center = mask[5:-5, 20] if vertical else mask[20, 5:-5]
    assert center.mean() > 0.9
    p = emit(field, valid, 0.22, "soft-ridge")
    assert np.isfinite(p).all() and p.min() >= 0 and p.max() <= 1
    assert np.count_nonzero(p) < 100


def test_flat_field_is_not_a_blanket_prediction():
    a = np.ones((30, 30), dtype="float32") * 0.5
    assert not ridge_mask(a, np.ones(a.shape, bool)).any()


def test_sampling_never_crosses_training_mask_and_is_deterministic():
    target = np.array([1, 1, 0.6, 0.3, 0, 0, 0, 1, 0, 0], dtype="float32")
    allow = np.array([1] * 7 + [0] * 3, bool)
    config = {"max_near_samples": 1, "max_unlabeled_samples": 2}
    a, summary = sample_rows(target, allow, config, 8)
    b, _ = sample_rows(target, allow, config, 8)
    assert set(a) <= set(range(7)) and {0, 1} <= set(a)
    assert summary["unlabeled"] == 2 and summary["near_positive"] == 1
    np.testing.assert_array_equal(a, b)


def test_selection_depends_on_tuning_not_audit():
    rows = [{"arm": "a", "eligible": True, "floor": 0.1, "emission": "soft-ridge",
             "tuning": {"dti": 0.2, "prediction_mass": 10}, "audit": {"dti": 0.99}},
            {"arm": "b", "eligible": True, "floor": 0.1, "emission": "soft-ridge",
             "tuning": {"dti": 0.3, "prediction_mass": 10}, "audit": {"dti": 0.01}}]
    assert choose_candidate(rows)["arm"] == "b"
    rows[1]["eligible"] = False
    assert choose_candidate(rows)["arm"] == "a"
    rows[0]["eligible"] = False
    with pytest.raises(ValueError, match="No nondegenerate"):
        choose_candidate(rows)


def test_tiny_cpu_training_handles_missing_features():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(150, 23)).astype("float32")
    x[:10, 2] = np.nan
    y = np.maximum(x[:, 0], 0).clip(0, 1)
    config = {"seed": 3, "model": {"max_iter": 3, "min_samples_leaf": 5, "early_stopping": False}}
    arm = {"context": True, "unlabeled_weight": 0.25}
    model = fit_arm(x, y, np.arange(150), arm, config)
    assert np.isfinite(model.predict(x)).all()
