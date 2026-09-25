import numpy as np
import pytest
import rasterio
from affine import Affine

from gems3.raster import template_info, validate_submission, write_submission

from .conftest import write_test_raster


def test_real_round_trip(template, tmp_path):
    valid, _ = template_info(template)
    p = np.full(valid.shape, 0.37, dtype="float32")
    out = tmp_path / "candidate.tif"
    report = write_submission(p, template, out)
    assert report["passed"] and report["counts"]["invalid_inside"] == 0
    assert report["counts"]["valid_pixels"] == int(valid.sum())
    with rasterio.open(out) as src:
        arr = src.read(1)
        np.testing.assert_array_equal(arr[valid], p[valid])
        assert np.isnan(arr[~valid]).all()
        assert src.crs.to_epsg() == 32611 and src.dtypes == ("float32",)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -0.001, 1.0001])
def test_exporter_refuses_bad_inside_without_touching_destination(template, tmp_path, bad):
    valid, _ = template_info(template)
    field = np.zeros(valid.shape, dtype="float32")
    field[4, 4] = bad
    out = tmp_path / "protected.tif"
    out.write_bytes(b"existing artifact")
    with pytest.raises(ValueError):
        write_submission(field, template, out)
    assert out.read_bytes() == b"existing artifact"
    assert not list(tmp_path.glob("*.pending.tif"))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -9999.0, 1.001])
def test_validator_catches_invalid_inside_even_if_minmax_looks_ok(template, tmp_path, bad):
    with rasterio.open(template) as src:
        a = src.read(1)
    a[5, 5] = bad
    path = write_test_raster(tmp_path / "bad.tif", template, a)
    report = validate_submission(path, template)
    assert not report["passed"]
    assert report["counts"]["invalid_inside"] or report["counts"]["out_of_range"]


@pytest.mark.parametrize("outside", [0.0, 1.0, np.inf, -np.inf])
def test_outside_must_be_nan_not_any_nonfinite(template, tmp_path, outside):
    with rasterio.open(template) as src:
        a = src.read(1)
    a[0, 0] = outside
    path = write_test_raster(tmp_path / "outside.tif", template, a)
    assert not validate_submission(path, template)["passed"]


@pytest.mark.parametrize("overrides", [{"count": 2}, {"dtype": "float64"}, {"nodata": None},
                                        {"crs": "EPSG:4326"},
                                        {"transform": Affine(100, 0, 243350.001, 0, -100, 4508550)}])
def test_spatial_and_container_gates(template, tmp_path, overrides):
    with rasterio.open(template) as src:
        arr = src.read(1)
    path = write_test_raster(tmp_path / "wrong.tif", template, arr, **overrides)
    assert not validate_submission(path, template)["passed"]


def test_shape_mismatch_and_corrupt_file(template, tmp_path):
    p = write_test_raster(tmp_path / "wrong-shape.tif", template, np.zeros((18, 23)), height=18)
    assert not validate_submission(p, template)["passed"]
    p.write_text("<html>Please log in</html>")
    assert not validate_submission(p, template)["passed"]
    assert not validate_submission(tmp_path / "missing.tif", template)["passed"]


def test_hidden_mask_holes_fail(template, tmp_path):
    valid, _ = template_info(template)
    out = tmp_path / "mask.tif"
    write_submission(np.full(valid.shape, 0.25, dtype="float32"), template, out)
    mask = valid.astype("uint8") * 255
    mask[5, 5] = 0
    with rasterio.open(out, "r+") as dst:
        dst.write_mask(mask)
    report = validate_submission(out, template)
    assert not report["passed"] and report["counts"]["mask_mismatches"] > 0


def test_sample_content_never_copied_as_predictions(template, tmp_path):
    with rasterio.open(template, "r+") as ref:
        arr = ref.read(1)
        arr[6, 6] = 1
        ref.write(arr, 1)
    valid, _ = template_info(template)
    out = tmp_path / "zero.tif"
    report = write_submission(np.zeros(valid.shape, dtype="float32"), template, out)
    with rasterio.open(out) as result:
        assert result.read(1)[6, 6] == 0
    assert report["passed"]  # zero is format-valid, even though pipeline rejects it as non-predictive


def test_empty_reference_and_bad_crs_are_not_trusted(template, tmp_path):
    bad = write_test_raster(tmp_path / "empty.tif", template, np.full((19, 23), np.nan))
    with pytest.raises(ValueError, match="no valid"):
        template_info(bad)
    with pytest.raises(ValueError, match="shape"):
        write_submission(np.zeros((2, 2)), template, tmp_path / "no.tif")


@pytest.mark.parametrize('bad', [1 + 1e-12, -1e-50])
def test_out_of_range_is_checked_before_float32_rounding(template, tmp_path, bad):
    valid, _ = template_info(template)
    p = np.zeros(valid.shape, dtype='float64')
    p[4, 4] = bad
    with pytest.raises(ValueError, match='outside'):
        write_submission(p, template, tmp_path/'bad-precision.tif')


def test_masked_input_cannot_hide_a_missing_inside_prediction(template, tmp_path):
    valid, _ = template_info(template)
    p = np.ma.array(np.zeros(valid.shape), mask=np.zeros(valid.shape, bool))
    p.mask[4, 4] = True
    with pytest.raises(ValueError, match='Masked prediction'):
        write_submission(p, template, tmp_path/'masked.tif')
