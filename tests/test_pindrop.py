"""Pindrop v4: the placement decision layer, the published portfolio and the live site wiring."""
from __future__ import annotations

import json

import numpy as np
import pytest
from scipy.ndimage import distance_transform_edt

from gems3.common import ROOT, read_json
from gems3.metric import MetricContext
from gems3.pindrop import policy_rank, robust_dti, score_emission
from gems3.raster import template_info, validate_submission
from gems3.schedule import MAX_SAFE_SPACING_PX, budget_count, prefix_field, suppression_order


def committed_template():
    """The same template CI has: `data/` is not committed, so the pinned bridge mirror is the fallback.

    The two files are byte-identical (sha256 2176d08e485aa2cd..., 5,167,373 template-valid pixels), which is
    asserted by the experiment's recorded input hash rather than assumed.
    """
    candidates = (ROOT / "data/sample_submission.tif", ROOT / "legacy/data/bridge/example_submission.tif")
    return next((c for c in candidates if c.exists()), None)


def base_candidate(**overrides):
    candidate = {"robust_dti": 0.2, "emitted_fraction": 0.02, "arm": "union-target", "layer": "nodes",
                 "spacing": 4, "budget": 0.02, "halo": 0, "tip": 0}
    candidate.update(overrides)
    return candidate


def test_policy_rank_is_deterministic_and_uses_the_frozen_order():
    better = base_candidate(robust_dti=0.21)
    cheaper = base_candidate(emitted_fraction=0.01)
    dense = base_candidate(layer="ridge", spacing=1)
    assert sorted([better, base_candidate()], key=policy_rank)[0] is better
    assert sorted([cheaper, base_candidate()], key=policy_rank)[0] is cheaper
    # On a tie the pre-registered key order breaks it, and "nodes" < "ridge", so the node layer wins a
    # tie: the control has to beat it on measured robust DTI, it cannot win by being denser.
    winner = sorted([dense, base_candidate()], key=policy_rank)[0]
    assert winner["layer"] == "nodes" and winner["spacing"] == 4
    assert policy_rank(base_candidate()) == policy_rank(base_candidate())


def test_robust_dti_is_the_minimum_of_the_registered_proxies():
    scored = {"gap": {"dti": 0.3}, "all": {"dti": 0.25}, "known": {"dti": 0.4}, "far": {"dti": 0.1}}
    assert robust_dti(scored) == pytest.approx(0.25)
    assert robust_dti(scored, ["gap", "far"]) == pytest.approx(0.1)


def test_supplied_label_proxy_ignores_tip_rays_but_gap_truth_does_not():
    shape = (9, 9)
    valid = np.ones(shape, dtype=bool)
    known = np.zeros(shape, dtype="int8")
    known[4, 2] = 1
    gap_truth = np.zeros(shape, dtype="int8")
    gap_truth[4, 6] = 1
    emission = np.zeros(shape, dtype="float32")
    emission[4, 3] = 1.0   # a tip-ray pixel one step beyond the supplied trace
    emission[4, 6] = 1.0   # a genuine node on gap truth
    tip_mask = np.zeros(shape, dtype=bool)
    tip_mask[4, 3] = True
    contexts = {"gap": MetricContext(gap_truth)}
    known_ctx = MetricContext(known)
    scored = score_emission(emission, tip_mask, contexts, known_ctx, valid, known)
    assert scored["gap"]["TP_w"] == pytest.approx(1.0)   # gap truth is credited, rays or not
    assert scored["known"]["TP_w"] == 0.0                 # the ray cannot credit its own trace
    # The supplied-label proxy drops the ray from the emission entirely: only the genuine node is
    # counted, so the ray can neither gain credit nor inflate that proxy's prediction mass.
    assert scored["known"]["prediction_pixels"] == 1
    assert scored["known"]["TP_w"] == 0.0
    unscored_rays = score_emission(emission, np.zeros(shape, dtype=bool), contexts, known_ctx, valid,
                                   known)
    assert unscored_rays["known"]["prediction_pixels"] == 2


def test_node_schedule_is_the_dense_prefix_when_spacing_is_one():
    rng = np.random.default_rng(3)
    field = rng.random((30, 30)).astype("float32")
    valid, known = np.ones((30, 30), bool), np.zeros((30, 30), bool)
    ridges = np.ones((30, 30), bool)
    dist_known = distance_transform_edt(~known).astype("float32")
    from gems3.schedule import candidate_pixels
    mask, score = candidate_pixels(field, valid, known, ridges, dist_known, 0)
    rows, cols = np.nonzero(mask)
    dense = suppression_order(rows, cols, score[rows, cols], 1)
    nodes = suppression_order(rows, cols, score[rows, cols], 5)
    # The dense order visits every candidate; the node order accepts a subset, best first.
    assert len(dense) == len(rows)
    assert len(nodes) < len(dense)
    assert np.all(np.diff(-score[rows[dense], cols[dense]]) >= 0)


def test_metric_algebra_constants_match_the_config_and_the_report():
    """The spacing bound is derived from the metric, and the configured layers must respect it.

    The config stores the derivation as prose (``metric_algebra``) and the numeric constants are
    materialised in the run report, so this test closes the loop: same radius, same bound, and no
    configured layer may space pixels further apart than the kernel can still cover.
    """
    cfg = read_json(ROOT / "configs/pindrop-v4.json")
    report = read_json(ROOT / "docs/data/pindrop-experiment.json")
    algebra = report["metric_algebra"]
    assert algebra["kernel_radius_px"] == 3 and algebra["pixel_denominator_cost"] == 0.2
    assert algebra["max_safe_spacing_px"] == 2 * algebra["kernel_radius_px"] - 1 == MAX_SAFE_SPACING_PX
    assert "spacing" in cfg["metric_algebra"].lower(), "the derivation must stay documented in the config"
    assert max(layer["spacing_px"] for layer in cfg["layers"]) <= MAX_SAFE_SPACING_PX
    assert (cfg["training_folds"], cfg["tuning_fold"], cfg["audit_fold"]) == ([1, 2], 3, 0)
    assert cfg["node_budget_fractions"][0] >= report["config"]["min_emitted_fraction"]
    assert budget_count(1000, 0.02, 10000) == 20
    assert set(np.unique(prefix_field(np.array([1]), np.array([1]), 1, (3, 3)))) <= {0.0, 1.0}


def test_published_pindrop_portfolio_is_valid_unique_and_unscored():
    """The live portfolio must be the pindrop-v4 files, fully re-hashable from disk."""
    import hashlib
    import zipfile

    manifest = read_json(ROOT / "docs/data/portfolio.json")
    assert manifest["strategy"] == "pindrop-v4"
    items = manifest["items"]
    # Order is value, not experiment number: the control is published last so the three weekly upload
    # slots are spent on the two files that have a measured reason to be believed.
    assert [i["variant"] for i in items] == ["nodes", "discovery", "ridge"]
    assert [i["order"] for i in items] == [1, 2, 3]
    assert [i["role"] for i in items] == ["primary", "independent", "control"]
    assert "CONTROL" in items[-1]["badge"]
    assert len({i["sha256"] for i in items}) == 3 and len({i["note"] for i in items}) == 3
    template = committed_template()
    for item in items:
        path = ROOT / "docs" / item["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert item["competition_score"] is None and "unsubmitted" in item["status"]
        assert item["on_known_pixels"] == 0
        assert item["sha256"][:10] in item["note"] and len(item["note"]) <= 120
        with zipfile.ZipFile(ROOT / "docs" / item["zip"]) as z:
            assert z.namelist() == [item["filename"]]
            assert hashlib.sha256(z.read(item["filename"])).hexdigest() == item["sha256"]
        assert template is not None, "one of the two identical template copies must exist"
        assert validate_submission(path, template)["passed"]
    archived = read_json(ROOT / "docs/data/portfolio-coverage-v3.json")
    assert [i["variant"] for i in archived["items"]] == ["fusion", "wide", "ml"]
    gapfinder = read_json(ROOT / "docs/data/portfolio-gapfinder-v2.json")
    hashes = {i["sha256"] for i in items}
    assert not (hashes & {i["sha256"] for i in archived["items"]})
    assert not (hashes & {i["sha256"] for i in gapfinder["items"]})


def test_upload_strip_leads_home_and_executive_summary_with_the_first_note():
    from bs4 import BeautifulSoup

    items = read_json(ROOT / "docs/data/portfolio.json")["items"]
    for name in ("index.html", "executive_summary.html"):
        html = (ROOT / "docs" / name).read_text()
        soup = BeautifulSoup(html, "html.parser")
        strip = soup.select_one("#submit-now")
        assert strip is not None, f"{name} must answer 'what do I upload?' above the fold"
        assert html.index('id="submit-now"') < html.index('id="portfolio"')
        assert [a["href"] for a in strip.select("a.strip-step")] == [i["file"] for i in items]
        assert items[0]["note"] in strip.get_text()


def test_pindrop_experiment_json_is_strict_and_free_of_score_claims():
    def reject(value):
        raise ValueError("Nonstandard JSON number: " + value)

    path = ROOT / "docs/data/pindrop-experiment.json"
    json.loads(path.read_text(), parse_constant=reject)
    report = read_json(path)
    assert report["status"].startswith("format-validated portfolio")
    assert set(report["competition_scores"].values()) == {None}
    assert report["config"]["name"] == "pindrop-v4"
    frozen = report["selection_frozen_sha256"]
    assert len(frozen) == 64 and all(c in "0123456789abcdef" for c in frozen)
    assert report["metric_algebra"]["max_safe_spacing_px"] == 5
    assert report["selected"]["budget"] >= report["config"]["min_emitted_fraction"]
    assert {row["role"] for row in report["audit"]} >= {"selected", "ridge-control", "arm-best"}
    assert report["audit_bootstrap"], "both pre-registered comparisons must be measured"
    assert all(row["dti"] is not None for row in report["tranche_tuning"])
    assert any("rotation" in text.lower() for text in report["limitations"])
    assert (report["partition"]["tuning_fold"], report["partition"]["audit_fold"]) == (3, 0), \
        "session 4 must not reuse an earlier session's tune/audit roles"
    # Closed loop: the published raster's own tags must name this run's frozen selection.
    import rasterio

    item = read_json(ROOT / "docs/data/portfolio.json")["items"][0]
    with rasterio.open(ROOT / "docs" / item["file"]) as src:
        tags = src.tags()
    assert tags["selection_sha256"] == frozen
    assert tags["strategy"] == "pindrop-v4" and tags["variant"] == "nodes"


def test_sparse_nodes_beat_the_dense_control_at_every_swept_budget():
    """The headline measurement, read back from the published JSON (not re-derived here)."""
    report = read_json(ROOT / "docs/data/pindrop-experiment.json")
    compared = 0
    for row in report["layer_comparison_tuning"]:
        dense, nodes4 = row.get("ridge@1"), row.get("nodes@4")
        if not dense or not nodes4:
            continue
        assert nodes4["gap_dti"] > dense["gap_dti"], f"node layer lost at budget {row['budget']}"
        assert nodes4["credit_per_emitted_pixel"] > dense["credit_per_emitted_pixel"]
        compared += 1
    assert compared >= 4, "the layer comparison must cover the swept budgets"


def test_archived_coverage_portfolio_files_are_still_published_and_valid():
    """Session 3's files stay downloadable, so their manifest must stay verifiable."""
    import hashlib

    template = committed_template()
    manifest = read_json(ROOT / "docs/data/portfolio-coverage-v3.json")
    for item in manifest["items"]:
        path = ROOT / "docs" / item["file"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert validate_submission(path, template)["passed"]


def test_publisher_refuses_a_report_whose_control_policy_contradicts_its_pixels():
    """Regression for the reviewed run-1 defect: the dense control recorded the selected node policy.

    The guard is what makes the defect unrepeatable: the pixels were always right, so only a check on
    the record itself can stop a mislabelled control (and its pasted Note) from being published.
    """
    from gems3.pindrop_publish import check_variant_policies

    run1 = read_json(ROOT / "evidence/pindrop-v4-run1-report.json")
    ridge = next(entry for entry in run1["portfolio"] if entry["variant"] == "ridge")
    assert ridge["policy"]["layer"] == "nodes", "run 1 must stay preserved exactly as it was written"
    with pytest.raises(ValueError, match="ridge"):
        check_variant_policies(run1)
    frozen = read_json(ROOT / "evidence/pindrop-v4-run1-selection-frozen.json")
    winner = frozen["winner"]
    assert {k: winner[k] for k in ("arm", "layer", "spacing", "budget", "halo", "tip")} == \
        {k: run1["selected"][k] for k in ("arm", "layer", "spacing", "budget", "halo", "tip")}
    assert frozen["audit_consulted"] is False, "the selection must stay frozen before any audit score"


def test_archived_portfolio_is_labelled_as_history_not_advice():
    """An archived manifest must not read like the current recommendation (review finding, pass 2)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup((ROOT / "docs/index.html").read_text(), "html.parser")
    live, previous = soup.select_one("#portfolio"), soup.select_one("#portfolio-previous")
    assert live is not None and previous is not None
    assert live.select_one("h2").get_text().startswith("Upload "), "the live block gives the instruction"
    assert "ARCHIVED" in previous.select_one(".eyebrow").get_text()
    assert previous.select_one("h2").get_text().startswith("Kept "), "history must not instruct"
    # and the live block must come first in document order
    html = str(soup)
    assert html.index('id="portfolio"') < html.index('id="portfolio-previous"')


def test_rendered_pages_have_no_duplicate_element_ids():
    """Duplicate ids break strict locators and assistive technology (found by the Chromium suite).

    The home page renders two portfolios (the live one and the archived session-3 one). Both carried
    id="portfolio-status" until the archived block was given its own id.
    """
    from bs4 import BeautifulSoup

    for path in sorted((ROOT / "docs").glob("*.html")):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        ids = [tag["id"] for tag in soup.find_all(attrs={"id": True})]
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        assert not duplicates, f"{path.name} repeats ids: {duplicates}"
    home = (ROOT / "docs/index.html").read_text()
    assert home.count('id="portfolio-status"') == 1
    assert 'id="portfolio-status-portfolio-previous"' in home


def test_pindrop_limitations_are_published_on_the_site():
    html = (ROOT / "docs/experiments.html").read_text()
    # The section is rendered from the published report: eyebrow upper-cased, run named by its id.
    assert "EXPERIMENT 004" in html and "PINDROP" in html
    assert "pindrop-v4" in html
    assert "not a hidden-label or leaderboard score" in html
    assert "Rotation, not independence" in html
    report = read_json(ROOT / "docs/data/pindrop-experiment.json")
    for text in report["limitations"]:
        assert text in html, f"limitation missing from the site: {text}"
    # The published preview must be shown with its honest caption, and the asset must exist.
    assert "assets/pindrop-preview.png" in html
    assert (ROOT / "docs/assets/pindrop-preview.png").is_file()
    assert "not a filled map" in html


def test_template_info_still_defines_the_footprint_used_by_the_sweep():
    template = committed_template()
    assert template is not None
    valid, profile = template_info(template)
    assert int(valid.sum()) == read_json(ROOT / "docs/data/pindrop-experiment.json")["valid_pixels"]
    assert profile["crs"].to_epsg() == 32611
