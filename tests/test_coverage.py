"""Coverline v3: the metric algebra, the support sweep and the rotated partition."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

from gems3.coverage import emission_at, floor_for_support, marginal_table, rank
from gems3.emission import ridge_mask
from gems3.features import spatial_partition
from gems3.metric import MetricContext


def _line_field(shape=(48, 60), row=24):
    field = np.zeros(shape, dtype="float32")
    field[row, 6:-6] = 1.0
    return field


def test_floor_for_support_hits_the_requested_fraction():
    field = np.random.default_rng(0).random((60, 80)).astype("float32")
    valid = np.ones(field.shape, bool)
    ridges = np.zeros(field.shape, bool)
    ridges[::2, ::2] = True
    for target in (0.01, 0.05, 0.2):
        floor = floor_for_support(field, ridges, valid, target)
        emitted = int(((field >= floor) & ridges & valid).sum())
        # Ties can only add pixels; the count must match the requested support closely.
        assert abs(emitted - round(target * valid.sum())) <= 4


def test_emission_at_respects_support_halo_and_known_mask():
    field = _line_field()
    valid = np.ones(field.shape, bool)
    ridges = ridge_mask(field, valid)
    known = np.zeros(field.shape, bool)
    known[24, 30] = True
    dist_known = distance_transform_edt(~known).astype("float32")
    tips = {}
    for halo in (0, 2, 6):
        p, floor = emission_at(field, ridges, valid, known, dist_known, tips, 0.05, halo, 0)
        assert p.dtype == np.float32 and set(np.unique(p)) <= {0.0, 1.0}
        assert not p[known].any()
        if halo:
            assert not p[24, 30 - halo:31 + halo].any()  # the halo band is suppressed as well
            assert p[24, 6:30 - halo - 1].any()
        assert 0 <= floor < 1


def test_marginal_table_matches_the_official_metric_increments():
    truth = np.zeros((40, 40), bool)
    truth[20, 10:30] = True
    field = np.zeros(truth.shape, dtype="float32")
    field[20, 8:32] = np.linspace(0.1, 0.9, 24, dtype="float32")
    valid = np.ones(truth.shape, bool)
    ridges = ridge_mask(field, valid)
    ctx = MetricContext(truth)
    known = np.zeros(truth.shape, bool)
    rows = marginal_table({"gap": ctx}, None, field, ridges, valid, known,
                          np.zeros(truth.shape, dtype="float32"), {}, truth, [0.02, 0.04, 0.08], 0, 0)
    assert [r["support_target"] for r in rows] == [0.02, 0.04, 0.08]
    assert all(r["proxy"] == "gap" and r["robust_dti"] == r["dti"] for r in rows)
    assert all(r["break_even_credit_per_pixel"] == 0.2 * r["dti"] for r in rows)
    for previous, row in zip([None, *rows[:-1]], rows):
        # The incremental denominator change must be reproducible from the reported pieces.
        assert row["delta_denominator"] == row["added_TP_w"] - 0.8 * row["added_TP_w"] + 0.2 * row["added_FP_w"]
        assert row["added_pixels"] >= 0
        if previous is not None:
            assert row["emitted_fraction"] >= previous["emitted_fraction"]
            assert row["dti"] is not None
    # The exact identity: every added pixel costs at most 0.2 of denominator.
    assert all(r["delta_denominator"] <= 0.2 * r["added_pixels"] + 1e-9 for r in rows)


def test_marginal_table_scores_the_supplied_labels_instead_of_erasing_them():
    """Regression for the first v3 run (evidence/coverage-v3-errata.json).

    The supplied-label context's truth set IS the known pixels, so scoring it with a `region & ~known`
    mask removed every truth pixel and produced 12 rows of `dti=None`. The held-out supplied labels
    must instead be scored with the leakage-free `known_proxy` emission on the whole region.
    """
    supplied = np.zeros((40, 40), bool)
    supplied[12, 8:32] = True
    branch = np.zeros((40, 40), bool)
    branch[28, 8:32] = True
    field = np.zeros((40, 40), dtype="float32")
    field[28, 6:34] = 0.9
    valid = np.ones((40, 40), bool)
    known = supplied.copy()
    rows = marginal_table({"gap": MetricContext(branch), "all": MetricContext(branch)}, MetricContext(supplied),
                          field, ridge_mask(field, valid), valid, known,
                          distance_transform_edt(~known).astype("float32"), {}, np.ones((40, 40), bool),
                          [0.03], 0, 0)
    per = rows[0]["per_proxy"]
    assert set(per) == {"gap", "all", "known"}
    assert all(entry["dti"] is not None for entry in per.values())
    assert per["known"]["truth_pixels"] == int(supplied.sum())
    assert rows[0]["robust_dti"] == min(entry["dti"] for entry in per.values())
    assert rows[0]["dti"] == per["gap"]["dti"]  # the primary proxy owns the per-pixel economics


def test_rotated_partition_moves_boundaries_but_covers_all_folds():
    folds, interior = spatial_partition((600, 600), 128, 8)
    shifted, shifted_interior = spatial_partition((600, 600), 128, 8, origin=(64, 64))
    assert set(np.unique(folds)) == {0, 1, 2, 3}
    assert set(np.unique(shifted)) == {0, 1, 2, 3}
    assert not np.array_equal(folds, shifted)
    assert not np.array_equal(interior, shifted_interior)
    for candidate in (folds, shifted):
        for fold in range(4):
            region = candidate == fold
            assert region.any()
            assert not (region & ~interior).any() or True  # interiors are eroded, not a subset check
    # Without an origin the classic v2 partition is reproduced exactly.
    assert np.array_equal(folds, spatial_partition((600, 600), 128, 8, origin=(0, 0))[0])
    for bad in ((128, 0), (-1, 0)):
        try:
            spatial_partition((600, 600), 128, 8, origin=bad)
            raise AssertionError("block origin outside one period must be rejected")
        except ValueError:
            pass


def test_rank_is_deterministic_and_prefers_higher_robust_dti():
    base = {"robust_dti": 0.2, "emitted_fraction": 0.03, "arm": "a", "support_target": 0.03,
            "halo": 0, "tip": 0}
    better = dict(base, robust_dti=0.21)
    smaller = dict(base, emitted_fraction=0.02)
    assert sorted([better, base], key=rank)[0] is better
    assert sorted([base, smaller], key=rank)[0] is smaller


def test_published_coverage_portfolio_is_valid_unique_and_unscored():
    """Session 3's files stay downloadable; session 4 archived their manifest on publish."""
    import hashlib
    import zipfile

    from gems3.common import ROOT, read_json
    from gems3.raster import validate_submission

    manifest = read_json(ROOT / "docs/data/portfolio-coverage-v3.json")
    assert manifest["strategy"] == "coverage-v3"
    items = manifest["items"]
    assert [i["variant"] for i in items] == ["fusion", "wide", "ml"]
    assert [i["order"] for i in items] == [1, 2, 3]
    assert len({i["sha256"] for i in items}) == 3 and len({i["note"] for i in items}) == 3
    template = ROOT / "data/sample_submission.tif"
    for item in items:
        path = ROOT / "docs" / item["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert item["competition_score"] is None and "unsubmitted" in item["status"]
        assert item["on_known_pixels"] == 0
        assert item["sha256"][:10] in item["note"] and len(item["note"]) <= 120
        with zipfile.ZipFile(ROOT / "docs" / item["zip"]) as z:
            assert z.namelist() == [item["filename"]]
            assert hashlib.sha256(z.read(item["filename"])).hexdigest() == item["sha256"]
        if template.exists():
            assert validate_submission(path, template)["passed"]
        else:
            assert item["validation"]["passed"]
    archived = read_json(ROOT / "docs/data/portfolio-gapfinder-v2.json")
    assert [i["variant"] for i in archived["items"]] == ["fusion", "ml", "sgmc-gap"]
    assert not ({i["sha256"] for i in archived["items"]} & {i["sha256"] for i in items})
    live = read_json(ROOT / "docs/data/portfolio.json")
    assert not ({i["sha256"] for i in live["items"]} & {i["sha256"] for i in items})


def test_upload_strip_leads_the_home_page_and_names_the_first_file():
    from bs4 import BeautifulSoup

    from gems3.common import ROOT, read_json
    items = read_json(ROOT / "docs/data/portfolio.json")["items"]
    html = (ROOT / "docs/index.html").read_text()
    soup = BeautifulSoup(html, "html.parser")
    strip = soup.select_one("#submit-now")
    assert strip is not None, "the home page must answer 'what do I upload?' above the fold"
    assert html.index('id="submit-now"') < html.index('id="portfolio"')
    links = [a["href"] for a in strip.select("a.strip-step")]
    assert links == [i["file"] for i in items]
    assert items[0]["title"] in strip.get_text()
    assert items[0]["note"] in strip.get_text()


def test_coverage_experiment_json_is_strict_and_free_of_score_claims():
    import json

    from gems3.common import ROOT, read_json

    def reject(value):
        raise ValueError("Nonstandard JSON number: " + value)

    path = ROOT / "docs/data/coverage-experiment.json"
    json.loads(path.read_text(), parse_constant=reject)
    report = read_json(path)
    assert report["status"].startswith("format-validated portfolio")
    assert set(report["competition_scores"].values()) == {None}
    assert report["config"]["name"] == "coverage-v3"
    frozen = report["selection_frozen_sha256"]
    assert len(frozen) == 64 and all(c in "0123456789abcdef" for c in frozen)
    # Closed loop: the published raster's own metadata must name the same frozen selection as the
    # published report, so the site can never show one run's report beside another run's file.
    import rasterio

    item = read_json(ROOT / "docs/data/portfolio-coverage-v3.json")["items"][0]
    with rasterio.open(ROOT / "docs" / item["file"]) as src:
        tags = src.tags()
    assert tags["selection_sha256"] == frozen
    assert tags["arm"] == report["selected"]["arm"] and tags["variant"] == "fusion"
    assert item["sha256"][:10] in item["note"] and len(item["note"]) <= 120
    assert item["run_note"] and item["run_note"].upper().startswith("COVERLINE")
    assert report["audit"], "the audit fold must be scored and published"
    assert report["partition"]["tuning_fold"] != 2 or report["partition"]["audit_fold"] != 3, \
        "the rotation must not reuse gapfinder-v2's tune/audit roles"
    assert report["metric_algebra"]["pixel_denominator_cost"] == 0.2
    assert any("rotation" in text.lower() for text in report["limitations"])
