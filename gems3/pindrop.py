"""Pindrop v4: spend a fixed pixel budget on suppression-spaced nodes instead of a dense line.

Read `gems3/schedule.py` for the metric argument and the falsifiable claims. This module is the
experiment runner: it trains two estimators, builds one ranked candidate schedule per (arm, spacing,
halo, tip), sweeps twelve emitted-pixel budgets on the tuning fold, freezes the winner, scores the
audit fold, refits the winning arm on the whole footprint and exports three format-validated files.

What is deliberately different from coverage-v3
-----------------------------------------------
1. One emission code path for both layers. `spacing = 1` suppresses nothing and therefore *is* the
   dense ridge control at a confidence floor; `spacing = 4 or 5` is the node schedule. A single
   parameter separates the hypothesis from its control, so the comparison cannot be confounded by a
   different floor rule, halo rule or tie-break.
2. Budgets are emitted pixels as a fraction of the valid footprint for *both* layers, i.e. the same
   resource the metric charges for.
3. A second training target: `discovery-target` trains only on catalogue pixels the supplied labels do
   not contain.
4. A third rotation of the spatial partition: origin (128, 128), train folds 1-2, tune 3, audit 0.

Honesty constraints (unchanged)
-------------------------------
* Train/tune/audit are distinct buffered block interiors; the rotation is disclosed as a rotation.
* The proxy catalogues are evaluation-only. Training targets are the supplied labels and the SGMC
  catalogue inside training folds, never a tuning or audit proxy.
* The recipe is frozen and hashed before any audit-fold statistic is computed.
* Nothing here is a hidden-label or leaderboard score, and no file is uploaded by this program.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import platform
import shutil
import time
from pathlib import Path

import numpy as np
import rasterio
import sklearn
from scipy.ndimage import distance_transform_edt

from .common import ROOT, read_json, sha256, utc_now, write_json
from .coverage import arm_field, kernel_target, stratified_rows
from .data import inspect_data
from .emission import ridge_mask
from .features import build_features, spatial_partition
from .gapfinder import (
    LEGACY,
    PROXY,
    PROXY_META,
    block_components,
    export,
    load_catalogues,
    paired_bootstrap,
)
from .geometry import extend_tips_parents, skeleton, tip_directions
from .metric import MetricContext
from .raster import template_info
from .schedule import (
    MAX_SAFE_SPACING_PX,
    budget_count,
    candidate_pixels,
    pairwise_separation,
    prefix_field,
    suppression_order,
)

SOURCE_FILES = ["common.py", "coverage.py", "data.py", "emission.py", "features.py", "gapfinder.py",
                "geometry.py", "metric.py", "raster.py", "schedule.py", "pindrop.py"]
PROXY_CODES = {"known": 1, "gap": 2}  # raster codes written by the pinned proxy builder
SELECTION_PROXIES = ["gap", "all", "known"]
FAR_DISTANCE_PX = 10


def source_digest() -> str:
    h = hashlib.sha256()
    for name in SOURCE_FILES:
        h.update(name.encode())
        h.update((ROOT / "gems3" / name).read_bytes())
    return h.hexdigest()


def load_catalogue_far(valid: np.ndarray, profile: dict, dist_known: np.ndarray) -> dict:
    """SGMC pixels at least 1 km from any supplied label: the 'far-field discovery' diagnostic."""
    if sha256(PROXY) != read_json(PROXY_META)["output"]["sha256"]:
        raise ValueError("Pinned SGMC raster changed; provenance review required")
    with rasterio.open(PROXY) as src:
        if src.shape != valid.shape or src.crs != profile["crs"] or src.transform != profile["transform"]:
            raise ValueError("SGMC raster is not on the exact competition grid")
        code = src.read(1)
    gap = (code == PROXY_CODES["gap"]) & valid
    return {"far": gap & (dist_known >= FAR_DISTANCE_PX), "gap": gap}


def build_schedule(field: np.ndarray, valid: np.ndarray, known: np.ndarray, ridges: np.ndarray,
                   dist_known: np.ndarray, tips: np.ndarray, tip_ids: np.ndarray | None, tip_px: int,
                   halo: int, spacing: int) -> dict:
    """Candidate ordering for one (spacing, halo, tip) policy of one arm."""
    rays = None
    ids = None
    if tip_px:
        if tip_ids is None:
            raise ValueError("Tip extension requested without parent indices")
        rays = tip_ids >= 0
        ids = tip_ids
    candidates, score = candidate_pixels(field, valid, known, ridges, dist_known, halo,
                                         tip_rays=rays, tip_ids=ids, tip_locations=tips)
    rows_all, cols_all = np.nonzero(candidates)
    if not len(rows_all):
        raise ValueError("No candidate pixels for this policy")
    order = suppression_order(rows_all, cols_all, score[rows_all, cols_all], spacing)
    rows, cols = rows_all[order], cols_all[order]
    tip_mask = np.zeros_like(valid)
    if rays is not None:
        tip_mask = rays & candidates
    return {"rows": rows, "cols": cols, "candidates": int(len(rows_all)),
            "tip_mask": tip_mask, "spacing": int(spacing), "halo": int(halo), "tip": int(tip_px)}


def score_emission(emission: np.ndarray, tip_mask: np.ndarray, contexts: dict, known_ctx: MetricContext,
                   region: np.ndarray, known: np.ndarray, far_ctx: MetricContext | None = None) -> dict:
    """Proxy scores for one emission on one fold interior.

    Supplied-label truth is scored without tip-ray pixels: a ray starts one pixel beyond a supplied
    trace and would collect kernel credit from the very truth that generated it (leak found in
    gapfinder v2 and never repeated since).
    """
    mask = region & ~known
    result = {name: ctx.score(emission, mask) for name, ctx in contexts.items()}
    if far_ctx is not None:
        result["far"] = far_ctx.score(emission, mask)
    result["known"] = known_ctx.score(np.where(tip_mask, 0.0, emission).astype("float32"), region)
    return result


def robust_dti(scored: dict, keys=SELECTION_PROXIES) -> float:
    return float(min(scored[k]["dti"] for k in keys))


def policy_rank(candidate: dict) -> tuple:
    """Pre-registered order: robust DTI first, then the cheapest emission, then the fixed key order."""
    return (-candidate["robust_dti"], candidate["emitted_fraction"], candidate["arm"], candidate["layer"],
            candidate["spacing"], candidate["budget"], candidate["halo"], candidate["tip"])


def run(config_path: Path, data_dir: Path, out: Path) -> dict:
    t0, started = time.monotonic(), utc_now()
    out.mkdir(parents=True, exist_ok=True)
    cfg = read_json(config_path)
    digest = source_digest()
    (out / "source").mkdir(exist_ok=True)
    for name in SOURCE_FILES:
        shutil.copyfile(ROOT / "gems3" / name, out / "source" / name)
    shutil.copyfile(config_path, out / "source/config.json")
    folds_used = {*cfg["training_folds"], cfg["tuning_fold"], cfg["audit_fold"]}
    if len(folds_used) != 4 or folds_used != {0, 1, 2, 3}:
        raise ValueError("Training, tuning and audit folds must be disjoint and cover 0-3")
    if (cfg["training_folds"], cfg["tuning_fold"], cfg["audit_fold"]) in (
            ([0, 1], 2, 3), ([0, 3], 1, 2)):
        raise ValueError("That fold-role assignment belongs to an earlier session; this run must rotate")
    if max(layer["spacing_px"] for layer in cfg["layers"]) > MAX_SAFE_SPACING_PX:
        raise ValueError("A spacing beyond the kernel Nyquist limit can only lose coverage")

    inputs = inspect_data(data_dir)
    template = data_dir / "sample_submission.tif"
    valid, profile = template_info(template)
    valid_count = int(valid.sum())
    cat = load_catalogues(valid, profile, data_dir)
    known = cat["known"]
    dist_known = distance_transform_edt(~known).astype("float32")
    far = load_catalogue_far(valid, profile, dist_known)
    folds, interior = spatial_partition(valid.shape, cfg["block_px"], cfg["buffer_px"],
                                        tuple(cfg["block_origin_px"]))
    train = valid & interior & np.isin(folds, cfg["training_folds"])
    tune = valid & interior & (folds == cfg["tuning_fold"])
    audit = valid & interior & (folds == cfg["audit_fold"])
    matrix, ids, fmeta = build_features(data_dir / "training_features.tif", valid, data_dir / "cache", cfg)
    sk = skeleton(known)
    tips, dirs = tip_directions(sk, lookback=8)
    tip_lengths = sorted({int(value) for value in cfg["tip_extension_px"] if value})
    tip_parents = {length: extend_tips_parents(tips, dirs, length, valid.shape) for length in tip_lengths}
    contexts = {"gap": MetricContext(cat["sgmc_gap"]), "all": MetricContext(cat["sgmc_all"])}
    far_ctx = MetricContext(far["far"])
    known_ctx = MetricContext(known)
    print(f"partition origin={cfg['block_origin_px']} train={int(train.sum()):,} tune={int(tune.sum()):,} "
          f"audit={int(audit.sum()):,} | tips={len(tips):,} | far truth={int(far['far'].sum()):,}",
          flush=True)
    write_json(out / "preregistered.json",
               {"created_at": started, "config": cfg, "config_sha256": sha256(config_path),
                "source_sha256": digest, "inputs": inputs["files"], "feature_cache": fmeta["key"],
                "tips": int(len(tips)), "valid_pixels": valid_count,
                "proxy_truth": {**{k: int(v.sum()) for k, v in cat.items()},
                                "far": int(far["far"].sum())},
                "partition": {"block_px": cfg["block_px"], "buffer_px": cfg["buffer_px"],
                              "origin_px": cfg["block_origin_px"], "train": int(train.sum()),
                              "tune": int(tune.sum()), "audit": int(audit.sum())}})

    arms, candidates, schedules_meta = [], [], []
    for arm in cfg["arms"]:
        positives = np.zeros_like(known)
        for key in arm["positives"]:
            positives |= cat[key]
        target = kernel_target(positives, ids)
        rows, summary = stratified_rows(target, train.ravel()[ids], cfg, cfg["seed"])
        print(f"\n[{arm['id']}] training on {len(rows):,} rows; positives "
              f"{int((target[rows] == 1).sum()):,}", flush=True)
        raw, clipped, detail = arm_field(arm, matrix, target, rows, cfg, valid, ids, out, "holdout")
        del target
        ridges = ridge_mask(raw, valid)
        field_best = None
        for layer in cfg["layers"]:
            for halo in cfg["halo_px"]:
                for tip in cfg["tip_extension_px"]:
                    schedule = build_schedule(raw, valid, known, ridges, dist_known, tips,
                                              tip_parents.get(tip) if tip else None, tip, halo,
                                              layer["spacing_px"])
                    separation = pairwise_separation(schedule["rows"], schedule["cols"])
                    schedules_meta.append({"arm": arm["id"], "layer": layer["id"],
                                           "spacing": layer["spacing_px"], "halo": halo, "tip": tip,
                                           "accepted_nodes": int(len(schedule["rows"])),
                                           "candidates": schedule["candidates"], **separation})
                    for budget in cfg["node_budget_fractions"]:
                        count = budget_count(valid_count, budget, len(schedule["rows"]))
                        emission = prefix_field(schedule["rows"], schedule["cols"], count, valid.shape)
                        emitted = float(emission.sum() / valid_count)
                        scored = score_emission(emission, schedule["tip_mask"], contexts, known_ctx,
                                                tune, known, far_ctx)
                        row = {"arm": arm["id"], "layer": layer["id"], "spacing": layer["spacing_px"],
                               "budget": budget, "halo": halo, "tip": tip,
                               "requested_nodes": int(count), "emitted_pixels": int(emission.sum()),
                               "emitted_fraction": emitted,
                               "eligible": bool(cfg["min_emitted_fraction"] <= emitted <= cfg["max_emitted_fraction"]),
                               "robust_dti": robust_dti(scored), "tuning": scored,
                               "nodes_available": int(len(schedule["rows"])),
                               "credit_per_emitted_pixel": float(scored["gap"]["TP_w"] / max(int(emission.sum()), 1)),
                               "gap_dti": float(scored["gap"]["dti"]), "all_dti": float(scored["all"]["dti"]),
                               "known_dti": float(scored["known"]["dti"]), "far_dti": float(scored["far"]["dti"])}
                        candidates.append(row)
                        if row["eligible"] and (field_best is None or policy_rank(row) < policy_rank(field_best)):
                            field_best = row
                        print(f"  {layer['id']:5s} k={layer['spacing_px']} h={halo} L={tip} "
                              f"budget={budget:.4f} n={count:,} gap={scored['gap']['dti']:.4f} "
                              f"all={scored['all']['dti']:.4f} known={scored['known']['dti']:.4f} "
                              f"credit/px={row['credit_per_emitted_pixel']:.4f}", flush=True)
                    del schedule
            gc.collect()
        arms.append({"arm": arm, "best": field_best, "clipped_confidence": clipped,
                     "samples": summary, **detail})
        del raw, ridges
        gc.collect()
    eligible = [c for c in candidates if c["eligible"]]
    if not eligible:
        raise ValueError("No eligible candidate")
    selected = sorted(eligible, key=policy_rank)[0]
    if not any(a["best"] is selected for a in arms):
        raise AssertionError("Per-arm best must include the globally selected policy")
    winner = next(a for a in arms if a["arm"]["id"] == selected["arm"])
    other = next(a for a in arms if a["arm"]["id"] != selected["arm"])
    print(f"\nFROZEN: {selected['arm']} / {selected['layer']} k={selected['spacing']} "
          f"budget={selected['budget']:.4f} h={selected['halo']} L={selected['tip']}", flush=True)

    frozen = out / "selection-frozen.json"
    write_json(frozen, {"frozen_at": utc_now(), "winner": selected, "rule": cfg["selection"],
                        "audit_consulted": False, "source_sha256": digest})
    frozen_sha = sha256(frozen)

    # ---- audit: diagnostic only, it cannot change the frozen recipe ----
    audit_rows, comps = [], {}
    for entry in (winner, other):
        arm_id = entry["arm"]["id"]
        raw = np.load(out / f"{arm_id}-holdout.npy")
        ridges = ridge_mask(raw, valid)
        for label, policy in (("selected", selected if entry is winner else None),
                              ("ridge-control", {**selected, "layer": "ridge", "spacing": 1} if entry is winner else None),
                              ("arm-best", entry["best"])):
            if policy is None:
                continue
            schedule = build_schedule(raw, valid, known, ridges, dist_known, tips,
                                      tip_parents.get(policy["tip"]) if policy["tip"] else None,
                                      policy["tip"], policy["halo"], policy["spacing"])
            count = budget_count(valid_count, policy["budget"], len(schedule["rows"]))
            emission = prefix_field(schedule["rows"], schedule["cols"], count, valid.shape)
            scored = score_emission(emission, schedule["tip_mask"], contexts, known_ctx, audit, known, far_ctx)
            comps[f"{arm_id}::{label}"] = {k: block_components(far_ctx if k == "far" else contexts[k],
                                                               emission, audit, known, cfg["block_px"])
                                           for k in ("gap", "all")}
            audit_rows.append({"arm": arm_id, "role": label, "policy": {k: policy[k] for k in
                               ("layer", "spacing", "budget", "halo", "tip")},
                               "emitted_fraction": float(emission.sum() / valid_count),
                               "audit": scored})
            print(f"AUDIT {arm_id} / {label}: gap={scored['gap']['dti']:.4f} all={scored['all']['dti']:.4f} "
                  f"known={scored['known']['dti']:.4f}", flush=True)
            del schedule, emission
        del raw, ridges
        gc.collect()

    references = {}
    ref_caveats = {
        "coverage-v3-fusion": "session 3 published the all-fold refit, so every fold here is IN-SAMPLE "
                              "for it, and its file contains the SGMC traces that the gap proxy itself is "
                              "built from: an upper bound, not a comparable score",
        "coverage-v3-ml": "session 3 published the all-fold refit, so every fold here is IN-SAMPLE for "
                          "this file: an upper bound, not a comparable score",
        "coverage-v3-wide": "session 3 published the all-fold refit, so every fold here is IN-SAMPLE for "
                            "this file: an upper bound, not a comparable score",
        "gapfinder-v2-fusion": "session 2 published the all-fold refit and its file contains the SGMC "
                               "traces the gap proxy is built from: doubly incomparable",
        "riftline-published": "session 1 trained on folds that include this audit region, so the audit "
                              "columns are IN-SAMPLE for it",
        "legacy-ens12": "training regions unknown here; possibly the artifact behind extradr19's 0.1563, "
                        "unproven",
    }
    ref_paths = (("coverage-v3-fusion", next((ROOT / "docs/downloads").glob("coverage-v3-fusion-*.tif"), None)),
                 ("coverage-v3-ml", next((ROOT / "docs/downloads").glob("coverage-v3-ml-*.tif"), None)),
                 ("coverage-v3-wide", next((ROOT / "docs/downloads").glob("coverage-v3-wide-*.tif"), None)),
                 ("gapfinder-v2-fusion", next((ROOT / "docs/downloads").glob("gapfinder-v2-fusion-*.tif"), None)),
                 ("riftline-published", next((ROOT / "docs/downloads").glob("riftline-*.tif"), None)),
                 ("legacy-ens12", LEGACY))
    for label, path in ref_paths:
        if path is None or not Path(path).exists():
            continue
        with rasterio.open(path) as src:
            q = np.where(np.isfinite(src.read(1)) & valid, src.read(1), 0).astype("float32")
        references[label] = {"file": Path(path).name, "sha256": sha256(path),
                             "tune": score_emission(q, np.zeros_like(valid), contexts, known_ctx, tune, known, far_ctx),
                             "audit": score_emission(q, np.zeros_like(valid), contexts, known_ctx, audit, known, far_ctx),
                             "caveat": ref_caveats[label]}
    bootstrap = {
        f"{winner['arm']['id']}::sparse vs dense": {
            k: paired_bootstrap(comps[f"{winner['arm']['id']}::selected"][k],
                                comps[f"{winner['arm']['id']}::ridge-control"][k])
            for k in ("gap", "all")},
        f"{winner['arm']['id']} vs {other['arm']['id']} (nodes)": {
            k: paired_bootstrap(comps[f"{winner['arm']['id']}::selected"][k],
                                comps[f"{other['arm']['id']}::arm-best"][k])
            for k in ("gap", "all")},
    }
    if sha256(frozen) != frozen_sha:
        raise RuntimeError("Frozen selection mutated during audit")

    # ---- layer comparison on the tuning fold: the headline measurement ----
    layer_table = []
    for budget in cfg["node_budget_fractions"]:
        row = {"budget": budget}
        for layer in cfg["layers"]:
            match = [c for c in candidates if c["arm"] == winner["arm"]["id"] and c["budget"] == budget
                     and c["layer"] == layer["id"] and c["spacing"] == layer["spacing_px"]
                     and c["halo"] == selected["halo"] and c["tip"] == selected["tip"]]
            if match:
                c = match[0]
                row[f"{layer['id']}@{layer['spacing_px']}"] = {
                    "gap_dti": c["gap_dti"], "all_dti": c["all_dti"], "known_dti": c["known_dti"],
                    "emitted_pixels": c["emitted_pixels"],
                    "credit_per_emitted_pixel": c["credit_per_emitted_pixel"]}
        layer_table.append(row)

    # ---- tranche table for the selected layer, assembled from the frozen sweep ----
    tranche = []
    previous = None
    for budget in cfg["node_budget_fractions"]:
        match = [c for c in candidates if c["arm"] == selected["arm"] and c["layer"] == selected["layer"]
                 and c["spacing"] == selected["spacing"] and c["budget"] == budget
                 and c["halo"] == selected["halo"] and c["tip"] == selected["tip"]]
        if not match:
            raise ValueError("Selected tranche missing from the sweep")
        s = match[0]["tuning"]["gap"]
        added_pixels = s["prediction_pixels"] - (previous["prediction_pixels"] if previous else 0)
        added_tp = s["TP_w"] - (previous["TP_w"] if previous else 0.0)
        added_fp = s["FP_w"] - (previous["FP_w"] if previous else 0.0)
        tranche.append({"budget": budget, "emitted_pixels": s["prediction_pixels"],
                        "emitted_fraction": match[0]["emitted_fraction"], "dti": s["dti"],
                        "added_pixels": int(added_pixels), "added_TP_w": float(added_tp),
                        "added_FP_w": float(added_fp),
                        "covered_credit_per_added_pixel": float(added_tp / added_pixels) if added_pixels else None,
                        "break_even_credit_per_pixel": (0.2 * s["dti"]) if s["dti"] is not None else None})
        previous = s
    if any(row["dti"] is None for row in tranche):
        raise ValueError("Tranche table has unscorable rows; the scoring mask is wrong")

    # ---- fraction-consistent refit of the frozen arm ----
    arm = next(a for a in cfg["arms"] if a["id"] == selected["arm"])
    positives = np.zeros_like(known)
    for key in arm["positives"]:
        positives |= cat[key]
    target = kernel_target(positives, ids)
    fractions = next(a["samples"]["fractions"] for a in arms if a["arm"]["id"] == arm["id"])
    rows, refit_summary = stratified_rows(target, valid.ravel()[ids], cfg, cfg["seed"], fractions=fractions)
    print(f"Refit {arm['id']} on {len(rows):,} rows (fraction-consistent)", flush=True)
    raw_refit, refit_clipped, refit_detail = arm_field(arm, matrix, target, rows, cfg, valid, ids, out, "refit")
    del target, positives
    gc.collect()

    def deploy(raw_field: np.ndarray, policy: dict) -> np.ndarray:
        ridges = ridge_mask(raw_field, valid)
        schedule = build_schedule(raw_field, valid, known, ridges, dist_known, tips,
                                  tip_parents.get(policy["tip"]) if policy["tip"] else None,
                                  policy["tip"], policy["halo"], policy["spacing"])
        count = budget_count(valid_count, policy["budget"], len(schedule["rows"]))
        return prefix_field(schedule["rows"], schedule["cols"], count, valid.shape)

    raw_hold = np.load(out / f"{winner['arm']['id']}-holdout.npy")
    p_refit, p_hold = deploy(raw_refit, selected), deploy(raw_hold, selected)
    s_refit, s_hold = float(p_refit[valid].mean()), float(p_hold[valid].mean())
    refit_ok = (cfg["min_emitted_fraction"] <= s_refit <= cfg["max_emitted_fraction"]
                and 1 / 1.5 <= s_refit / max(s_hold, 1e-12) <= 1.5)
    if refit_ok:
        deployed_raw, nodes_field, role = raw_refit, p_refit, "all-fold refit (fraction-consistent sampling)"
    else:
        deployed_raw, nodes_field, role = raw_hold, p_hold, "frozen holdout model (refit rejected by pre-registered gate)"
    deployed_model = (refit_detail["model_file"] if refit_ok
                      else next(a["model_file"] for a in arms if a["arm"]["id"] == selected["arm"]))
    deployment = {"refit_support": s_refit, "holdout_support": s_hold, "refit_accepted": bool(refit_ok),
                  "model_role": role, "model_file": deployed_model,
                  "model_sha256": sha256(out / deployed_model),
                  "policy": {k: selected[k] for k in ("layer", "spacing", "budget", "halo", "tip")},
                  "refit_samples": refit_summary, "refit_clipped": refit_clipped}
    del p_refit, p_hold
    gc.collect()

    # ---- three-file portfolio ----
    ridge_field = deploy(deployed_raw, {**selected, "layer": "ridge", "spacing": 1})
    other_policy = other["best"]
    other_raw = np.load(out / f"{other['arm']['id']}-holdout.npy")
    discovery_field = deploy(other_raw, other_policy)
    del other_raw
    gc.collect()
    fields = {"nodes": nodes_field, "ridge": ridge_field, "discovery": discovery_field}
    with rasterio.open(LEGACY) as src:
        legacy = np.where(valid, src.read(1), 0)
    previous_files = {}
    for label, pattern in (("coverage-v3", "coverage-v3-fusion-*.tif"), ("gapfinder-v2", "gapfinder-v2-fusion-*.tif"),
                           ("riftline", "riftline-*.tif")):
        path = next((ROOT / "docs/downloads").glob(pattern), None)
        if path is not None:
            with rasterio.open(path) as src:
                previous_files[label] = np.where(valid, src.read(1), 0)
    arm_short = {"union-target": "union-target HGB", "discovery-target": "discovery-target HGB"}
    portfolio = []
    for variant, field in fields.items():
        if variant == "discovery":
            policy, arm_id = other_policy, other["arm"]["id"]
        elif variant == "ridge":
            # The dense control is produced by the selected policy with the suppression disabled, so
            # that -- not the selected node policy -- is the policy this file records.
            policy, arm_id = {**selected, "layer": "ridge", "spacing": 1}, selected["arm"]
        else:
            policy, arm_id = selected, selected["arm"]
        field = np.where(valid, field, 0).astype("float32")
        policy_text = (f"{policy['layer']} k={policy['spacing']} budget={policy['budget']:.4f} "
                       f"h={policy['halo']} L={policy['tip']}")
        tags = {"strategy": cfg["name"], "variant": variant, "arm": arm_id, "policy": policy_text,
                "selection_sha256": frozen_sha, "seed": str(cfg["seed"])}
        name, zname, report = export(field, template, out, variant, tags,
                                     f"Pindrop {variant}: suppression-spaced binary fault nodes; "
                                     f"not calibrated probability", prefix=cfg["name"])
        idtag = report["sha256"][:10]
        # The Note is the only part of a submission a human types, so it names the file's own policy
        # and carries the hash prefix: two submissions can never share a Note, and a Note can always be
        # traced back to the exact bytes it describes.
        suffix = {"nodes": "sparse nodes", "ridge": "dense ridge control",
                  "discovery": "catalogue-gap"}[variant]
        shape_text = (f"k={policy['spacing']} s={policy['budget']:.3%} h={policy['halo']} L={policy['tip']}"
                      if policy["layer"] == "nodes" else
                      f"s={policy['budget']:.3%} h={policy['halo']} L={policy['tip']}")
        note = f"Pindrop v4 {variant} | {arm_short[arm_id]} | {suffix} {shape_text} | {idtag}"
        if len(note) > 120:
            raise ValueError(f"Note is {len(note)} characters; keep it under 120")
        diff = {"vs_legacy_ens12": int(np.count_nonzero(field[valid] != legacy[valid]))}
        for label, other_field in previous_files.items():
            diff[f"vs_{label}"] = int(np.count_nonzero(field[valid] != other_field[valid]))
        portfolio.append({"variant": variant, "file": name, "zip": zname, "sha256": report["sha256"],
                          "bytes": report["bytes"], "note": note, "validation": report,
                          "emitted_pixels": int((field[valid] > 0).sum()),
                          "emitted_fraction": float((field[valid] > 0).mean()),
                          "on_known_pixels": int((field[known] > 0).sum()),
                          "policy": {k: policy[k] for k in ("layer", "spacing", "budget", "halo", "tip")},
                          "arm": arm_id, "different_pixels": diff})
        print(f"PASS {name}\n  NOTE: {note}", flush=True)
    if source_digest() != digest:
        raise RuntimeError("Source changed during run")

    report = {"schema_version": 1, "name": "Pindrop", "strategy": cfg["name"], "started_at": started,
              "completed_at": utc_now(), "seconds": round(time.monotonic() - t0, 1),
              "status": "format-validated portfolio; unsubmitted; competition scores unknown",
              "competition_scores": {v["variant"]: None for v in portfolio},
              "config": cfg, "config_sha256": sha256(config_path), "source_sha256": digest,
              "environment": {"python": platform.python_version(), "numpy": np.__version__,
                              "sklearn": sklearn.__version__, "rasterio": rasterio.__version__,
                              "compute": "CPU, 2 threads, no GPU"},
              "inputs": inputs["files"], "sgmc_raster_sha256": sha256(PROXY),
              "catalogue_pixels": {**{k: int(v.sum()) for k, v in cat.items()},
                                   "far": int(far["far"].sum())},
              "tips_used": int(len(tips)), "valid_pixels": valid_count,
              "partition": {"training_folds": cfg["training_folds"], "tuning_fold": cfg["tuning_fold"],
                            "audit_fold": cfg["audit_fold"], "buffer_px": cfg["buffer_px"],
                            "origin_px": cfg["block_origin_px"], "train_pixels": int(train.sum()),
                            "tune_pixels": int(tune.sum()), "audit_pixels": int(audit.sum())},
              "metric_algebra": {
                  "pixel_denominator_cost": 0.2,
                  "kernel_radius_px": 3,
                  "max_safe_spacing_px": MAX_SAFE_SPACING_PX,
                  "coverage_half_gap_px_for_published_spacing": selected["spacing"] / 2.0,
                  "note": "A truth pixel is credited by the single best prediction inside the 300 m "
                          "kernel, so predictions spaced at half the kernel keep full coverage while "
                          "removing redundant false-positive mass."},
              "arms": arms, "candidates": candidates, "schedules": schedules_meta,
              "selected": selected, "ridge_control": {**selected, "layer": "ridge", "spacing": 1},
              "other_arm_candidate": other_policy, "selection_frozen_sha256": frozen_sha,
              "layer_comparison_tuning": layer_table, "tranche_tuning": tranche,
              "audit": audit_rows, "audit_bootstrap": bootstrap, "references": references,
              "deployment": deployment, "portfolio": portfolio,
              "limitations": [
                  "Local truth is the public SGMC layer and the supplied labels, never the hidden expert labels.",
                  "The partition is a third rotation of the same lattice; the footprint necessarily overlaps earlier sessions.",
                  "A sparse node emission is a metric-aware encoding, not evidence that faults are dotted in reality; the dense control is published beside it.",
                  "Supplied-label proxy scoring excludes tip rays for both layers, so the `known` column is not the deployed file's score there.",
                  "No third independent fault catalogue, no 1 m DEM, no GPU, no hidden labels, no authenticated upload."]}
    write_json(out / "experiment.json", report)
    print(f"\nDone in {report['seconds']} s. No competition score has been measured.", flush=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/pindrop-v4.json")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    output = args.output or ROOT / "outputs" / read_json(args.config)["name"]
    run(args.config, args.data, output)


if __name__ == "__main__":
    main()
