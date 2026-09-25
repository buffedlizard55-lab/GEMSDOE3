"""Gapfinder geometry, sampling, emission, bootstrap and published-portfolio regressions."""
import hashlib
import zipfile

import numpy as np
import pytest

from gems3.common import ROOT, read_json
from gems3.gapfinder import emit, known_proxy, paired_bootstrap, stratified_rows
from gems3.geometry import endpoints, extend_tips, skeleton, tip_directions, truncate_tips
from gems3.metric import MetricContext
from gems3.raster import validate_submission


def horizontal_line(shape=(40, 60), row=20, c0=10, c1=40):
    m = np.zeros(shape, bool)
    m[row, c0:c1] = True
    return m


def test_endpoints_and_outward_directions_of_a_straight_trace():
    sk = skeleton(horizontal_line())
    tips = {tuple(t) for t in endpoints(sk)}
    assert tips == {(20, 10), (20, 39)}
    t, d = tip_directions(sk, lookback=8)
    lookup = {tuple(a): b for a, b in zip(t, d)}
    assert lookup[(20, 39)] == pytest.approx([0, 1], abs=1e-9)   # east end points east
    assert lookup[(20, 10)] == pytest.approx([0, -1], abs=1e-9)  # west end points west


def test_extension_continues_along_strike_and_excludes_the_tip():
    sk = skeleton(horizontal_line())
    t, d = tip_directions(sk)
    ext = extend_tips(t, d, 5, sk.shape)
    assert ext.sum() == 10 and not (ext & sk).any()
    assert ext[20, 40:45].all() and ext[20, 5:10].all()
    assert not extend_tips(t, d, 0, sk.shape).any()


def test_extension_is_clipped_at_the_grid_edge():
    sk = skeleton(horizontal_line(c0=45, c1=60))
    t, d = tip_directions(sk)
    ext = extend_tips(t, d, 20, sk.shape)  # east ray leaves the grid: no wraparound or error
    assert ext[:, :45].sum() == 20 and ext[:, 45:].sum() == 0


def test_truncation_self_test_removes_exact_tip_lengths():
    sk = skeleton(horizontal_line())
    kept, removed = truncate_tips(sk, 5)
    assert removed.sum() == 10 and kept.sum() == sk.sum() - 10 and not (kept & removed).any()
    # A strand shorter than the cut is left intact rather than deleted entirely.
    short = skeleton(horizontal_line(c0=10, c1=13))
    k2, r2 = truncate_tips(short, 5)
    assert r2.sum() == 0 and k2.sum() == short.sum()


def test_fraction_consistent_refit_preserves_the_class_mixture():
    rng = np.random.default_rng(0)
    target = np.zeros(200_000, "float32")
    target[rng.choice(200_000, 2_000, replace=False)] = 1
    near = rng.choice(np.flatnonzero(target == 0), 20_000, replace=False)
    target[near] = 0.5
    allowed = np.zeros(200_000, bool)
    allowed[:50_000] = True
    cfg = {"max_near_samples": 1_000, "max_unlabeled_samples": 5_000}
    _, hold = stratified_rows(target, allowed, cfg, 1)
    _, refit = stratified_rows(target, np.ones_like(allowed), cfg, 1, fractions=hold["fractions"])
    assert refit["positive_share"] == pytest.approx(hold["positive_share"], abs=0.01)
    # The old capped-count sampler would have kept the caps while positives quadrupled.
    assert refit["unlabeled"] > cfg["max_unlabeled_samples"]


def test_emission_zeroes_known_pixels_applies_halo_and_is_binary():
    shape = (30, 30)
    valid = np.ones(shape, bool)
    known = np.zeros(shape, bool)
    known[15, 5:25] = True
    from scipy.ndimage import distance_transform_edt
    dk = distance_transform_edt(~known)
    raw = np.full(shape, 0.9, "float32")
    ridges = np.zeros(shape, bool)
    ridges[14:17, :] = True  # ridge on and beside the known trace
    ridges[5, :] = True       # an independent ridge far away
    p0 = emit(raw, ridges, valid, known, dk, {}, 0.5, 0, 0)
    p1 = emit(raw, ridges, valid, known, dk, {}, 0.5, 1, 0)
    assert set(np.unique(p0)) <= {0.0, 1.0}
    assert not p0[known].any() and not p1[known].any()
    assert p0[14, 10] == 1 and p1[14, 10] == 0  # adjacent halo pixel suppressed only with halo=1
    assert p1[5, 10] == 1                         # far ridge survives
    assert not emit(raw, ridges, valid, known, dk, {}, 0.95, 0, 0).any()


def test_known_proxy_scores_supplied_faults_without_the_organiser_mask():
    shape = (30, 30)
    valid = np.ones(shape, bool)
    known = np.zeros(shape, bool)
    known[15, 5:25] = True
    raw = np.where(known, 0.9, 0.0).astype("float32")
    r = known_proxy(MetricContext(known), raw, known.copy(), valid, 0.5, valid)
    assert r["dti"] == pytest.approx(1.0, abs=1e-6)


def test_paired_bootstrap_detects_a_uniformly_better_candidate():
    rng = np.random.default_rng(3)
    base = np.column_stack([rng.uniform(50, 100, 12), rng.uniform(500, 900, 12), rng.uniform(100, 200, 12)])
    better = base.copy()
    better[:, 0] += 30
    better[:, 2] -= 30
    out = paired_bootstrap(better, base, n=500)
    assert out["observed_difference"] > 0 and out["p_a_better"] == 1.0 and out["ci95"][0] > 0
    same = paired_bootstrap(base, base, n=200)
    assert same["observed_difference"] == 0 and same["ci95"] == [0, 0]


def test_published_portfolio_is_valid_unique_and_unscored():
    manifest = read_json(ROOT / "docs/data/portfolio.json")
    items = manifest["items"]
    assert [i["variant"] for i in items] == ["fusion", "ml", "sgmc-gap"]
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
        if template.exists():  # full raster validation needs the restored competition template
            assert validate_submission(path, template)["passed"]
        else:
            assert item["validation"]["passed"]


def test_portfolio_is_distinct_from_every_earlier_published_file():
    manifest = read_json(ROOT / "docs/data/portfolio.json")
    earlier = read_json(ROOT / "docs/data/submission.json")
    hashes = {i["sha256"] for i in manifest["items"]}
    assert earlier["artifact"]["sha256"] not in hashes
    assert earlier["note"] not in {i["note"] for i in manifest["items"]}
    legacy = ROOT / "legacy/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif"
    if legacy.exists():
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() not in hashes


def test_portfolio_leads_home_and_summary_with_direct_downloads_and_notes():
    from bs4 import BeautifulSoup
    items = read_json(ROOT / "docs/data/portfolio.json")["items"]
    for name in ["index.html", "executive_summary.html"]:
        html = (ROOT / "docs" / name).read_text()
        soup = BeautifulSoup(html, "html.parser")
        section = soup.select_one("#portfolio")
        assert section is not None
        assert html.index('id="portfolio"') < html.index('id="submission"'), "portfolio must precede Riftline"
        links = [a["href"] for a in section.select("a.portfolio-download")]
        assert links == [i["file"] for i in items]
        for item in items:
            note = section.select_one(f"#note-{item['variant']}")
            assert note is not None and note.get_text() == item["note"]
            assert section.select_one(f'button.copy-portfolio-note[data-target="note-{item["variant"]}"]')
        assert "Unknown until uploaded" in section.get_text()
