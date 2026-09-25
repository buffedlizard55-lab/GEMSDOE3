from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine


@pytest.fixture
def template(tmp_path):
    path = tmp_path / "template.tif"
    field = np.zeros((19, 23), dtype="float32")
    field[:2, :] = np.nan
    field[-1, :5] = np.nan
    profile = dict(driver="GTiff", height=19, width=23, count=1, dtype="float32", crs="EPSG:32611",
                   transform=Affine(100, 0, 243350, 0, -100, 4508550), nodata=np.nan)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(field, 1)
    return path


def write_test_raster(path: Path, template, values, **overrides):
    with rasterio.open(template) as src:
        profile = src.profile.copy()
    profile.update(overrides)
    array = np.asarray(values).astype(profile["dtype"])
    with rasterio.open(path, "w", **profile) as dst:
        if array.ndim == 2:
            for i in range(1, profile["count"] + 1):
                dst.write(array, i)
        else:
            dst.write(array)
    return path
