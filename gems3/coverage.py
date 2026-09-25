"""Coverline v3: pick the emission support from the official metric's own algebra.

Why this is not gapfinder-v2 with different numbers
--------------------------------------------------
The official metric page (verified 2026-09-25) defines the distance-weighted Tversky index with
alpha = 0.2, beta = 0.8 and a triangular kernel k(d) = max(1 - d/300 m, 0) at 100 m pixels:

    DTI = TP_w / (TP_w + alpha*FP_w + beta*FN_w)

For a binary emission at p = 1, adding one pixel x changes the denominator by

    delta D = 0.2*(coverage credit x newly contributes) + 0.2*(1 - k(d_x))

because a pixel that becomes the best cover of a truth pixel adds 1 to TP_w and removes 0.8 from
FN_w, while its own false-positive weight is 1 - k(d_x). Both terms are bounded by 0.2, so:

  * every emitted pixel costs at most 0.2 of denominator, and exactly 0.2 when nothing else near it
    covers hidden truth;
  * an emitted pixel pays for itself only if it sits within the 300 m kernel of hidden truth that no
    other emitted pixel covers;
  * the score rises iff (new coverage credit) > 0.2 * current score. At the public leader's 0.3049
    that break-even is 0.061, i.e. roughly within 2.8 px of uncovered truth.

So the design problem is *coverage per emitted pixel*, not classification accuracy. v2 searched five
hand-picked confidence floors; v3 searches twelve data-driven support levels, adds a beta/alpha
weighted classifier (the textbook Tversky surrogate) next to the regression control, rotates the
spatial partition, and publishes the per-tranche marginal value of every support step.

Honesty constraints (unchanged from gapfinder):
  * train/tune/audit are disjoint block interiors with a 48 px buffer; the rotation is disclosed as a
    rotation, never as an independent survey area;
  * SGMC is a training target only inside training folds;
  * the recipe is frozen and hashed before the audit fold is scored;
  * nothing here is a hidden-label or leaderboard score.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import platform
import shutil
import time
from pathlib import Path

import joblib
import numpy as np
import rasterio
import sklearn
from scipy.ndimage import distance_transform_edt
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .common import ROOT, read_json, sha256, utc_now, write_json
from .data import inspect_data
from .emission import ridge_mask
from .features import build_features, spatial_partition
from .gapfinder import (
    LEGACY,
    PROXY,
    block_components,
    emit,
    export,
    faithful,
    fit,
    kernel_target,
    known_proxy,
    load_catalogues,
    paired_bootstrap,
    predict,
    stratified_rows,
)
from .geometry import extend_tips, skeleton, tip_directions
from .metric import MetricContext
from .raster import template_info

SOURCE_FILES = ["common.py", "data.py", "emission.py", "features.py", "gapfinder.py", "geometry.py",
                "metric.py", "raster.py", "coverage.py"]


def source_digest() -> str:
    h = hashlib.sha256()
    for name in SOURCE_FILES:
        h.update(name.encode())
        h.update((ROOT / "gems3" / name).read_bytes())
    return h.hexdigest()


def floor_for_support(field: np.ndarray, ridges: np.ndarray, valid: np.ndarray, target: float) -> float:
    """Floor value whose oriented-ridge emission covers ~`target` of the valid grid.

    The sweep is therefore stated in the unit that the metric actually cares about (emitted pixels),
    not in an arbitrary confidence unit whose meaning changes between model arms.
    """
    if not 0 < target < 1:
        raise ValueError("Support target must be inside (0, 1)")
    values = np.asarray(field)[np.asarray(valid) & np.asarray(ridges)]
    if values.size == 0:
        raise ValueError("No oriented-ridge pixels on the valid grid; the sweep has nothing to rank")
    count = max(1, min(int(round(target * int(valid.sum()))), values.size))
    return float(np.partition(values, values.size - count)[values.size - count])


def emission_at(field: np.ndarray, ridges: np.ndarray, valid: np.ndarray, known: np.ndarray,
                dist_known: np.ndarray, tips_ext: dict, target: float, halo: int, tip: int):
    """Binary emission at a support target, plus the floor that produced it."""
    floor = floor_for_support(field, ridges, valid, target)
    return emit(field, ridges, valid, known, dist_known, tips_ext, floor, halo, tip), floor


def marginal_table(contexts: dict, known_ctx, field: np.ndarray, ridges: np.ndarray, valid: np.ndarray,
                   known: np.ndarray, dist_known: np.ndarray, tips_ext: dict, region: np.ndarray,
                   targets: list[float], halo: int, tip: int) -> list[dict]:
    """Exact, nested-tranche accounting of what each support step buys and costs.

    Tranches are nested (a higher support contains the lower one), so the difference between two rows
    is exactly the set of pixels the extra support adds. The per-pixel economics are stated on ONE
    proxy -- the first `contexts` entry, which is the pre-registered primary SGMC branch -- so that
    `covered_credit_per_added_pixel` and `break_even_credit_per_pixel` are directly comparable.
    `per_proxy` and `robust_dti` carry the other branches (the held-out supplied labels are scored
    with the leakage-free `known_proxy` emission, exactly as in the selection sweep), so the row's
    headline DTI is never a number that only one branch produced. A table whose rows cannot be scored
    is a bug, not a diagnostic: an unresolvable row raises.

    Erratum: the first v3 run scored `known_ctx` with mask `region & ~known`, which erases that
    context's entire truth set (the supplied labels ARE the known pixels) and yielded 12 rows of
    `dti=None`. See evidence/coverage-v3-errata.json.
    """
    rows, previous, primary = [], None, next(iter(contexts))
    for target in targets:
        p, floor = emission_at(field, ridges, valid, known, dist_known, tips_ext, target, halo, tip)
        per = faithful(contexts, p, region, known)
        if known_ctx is not None:
            per["known"] = known_proxy(known_ctx, field, ridges, valid, floor, region)
        s = per[primary]
        if previous is None:
            added_pixels, added_tp = s["prediction_pixels"], s["TP_w"]
            added_fp = s["FP_w"]
        else:
            added_pixels = s["prediction_pixels"] - previous["prediction_pixels"]
            added_tp = s["TP_w"] - previous["TP_w"]
            added_fp = s["FP_w"] - previous["FP_w"]
        delta_d = added_tp - 0.8 * added_tp + 0.2 * added_fp
        row = {"support_target": target, "floor": floor, "emitted_fraction": float(p[region].mean()),
               "proxy": primary, "dti": s["dti"], "TP_w": s["TP_w"], "FP_w": s["FP_w"], "FN_w": s["FN_w"],
               "robust_dti": min(entry["dti"] for entry in per.values()),
               "per_proxy": {k: {"dti": v["dti"], "TP_w": v["TP_w"], "FP_w": v["FP_w"], "FN_w": v["FN_w"],
                                 "truth_pixels": v["truth_pixels"]} for k, v in per.items()},
               "added_pixels": int(added_pixels), "added_TP_w": float(added_tp),
               "added_FP_w": float(added_fp),
               "covered_credit_per_added_pixel": (float(added_tp / added_pixels) if added_pixels else None),
               "break_even_credit_per_pixel": (0.2 * s["dti"] if s["dti"] is not None else None),
               "delta_denominator": float(delta_d)}
        rows.append(row)
        previous = s
    if any(r["dti"] is None for r in rows):
        raise ValueError("Marginal table has unscorable tranches; the scoring mask is wrong")
    return rows


def fit_classifier(matrix, target: np.ndarray, rows: np.ndarray, config: dict, positive_weight: float):
    """beta/alpha-weighted binary classifier: the standard surrogate for the scored Tversky index."""
    y = (target[rows] == 1).astype("int8")
    weights = np.where(y == 1, float(positive_weight), 1.0)
    model = HistGradientBoostingClassifier(random_state=config["seed"], **config["model"])
    x = np.array(matrix[rows], dtype="float32", copy=True)
    with threadpool_limits(limits=2):
        model.fit(x, y, sample_weight=weights)
    del x
    return model


def predict_probability(model, matrix, ids, shape):
    out = np.zeros(int(np.prod(shape)), dtype="float32")
    with threadpool_limits(limits=2):
        for start in range(0, len(ids), 65536):
            stop = min(start + 65536, len(ids))
            v = model.predict_proba(np.asarray(matrix[start:stop]))[:, 1]
            if not np.isfinite(v).all():
                raise ValueError("Nonfinite classifier output")
            out[ids[start:stop]] = np.clip(v, 0, 1)
    return out.reshape(shape), 0


def rank(candidate: dict) -> tuple:
    return (-candidate["robust_dti"], candidate["emitted_fraction"], candidate["arm"],
            candidate["support_target"], candidate["halo"], candidate["tip"])


def arm_field(arm: dict, matrix, target: np.ndarray, rows: np.ndarray, config: dict, valid: np.ndarray,
              ids: np.ndarray, out: Path, tag: str):
    """Train one arm and return its raw confidence field plus the logging record.

    `tag` names the saved artifacts so the fraction-consistent refit can never overwrite the
    frozen holdout model or its confidence field.
    """
    started = time.monotonic()
    if arm["objective"] == "kernel-regression":
        model = fit(matrix, target, rows, config)
        raw, clipped = predict(model, matrix, ids, valid.shape)
        detail = {"objective": "kernel-regression", "sample_weights": "kernel target in [0,1]"}
    elif arm["objective"] == "weighted-classification":
        model = fit_classifier(matrix, target, rows, config, arm["positive_weight"])
        raw, clipped = predict_probability(model, matrix, ids, valid.shape)
        detail = {"objective": "weighted-classification", "positive_weight": arm["positive_weight"],
                  "positive_rows": int((target[rows] == 1).sum())}
    else:
        raise ValueError(f"Unknown objective {arm['objective']}")
    model_file = f"{arm['id']}-{tag}.joblib"
    joblib.dump(model, out / model_file, compress=3)
    del model
    np.save(out / f"{arm['id']}-{tag}.npy", raw)
    return raw, clipped, {"seconds": round(time.monotonic() - started, 1), "model_file": model_file, **detail}


def run(config_path: Path, data_dir: Path, out: Path) -> dict:
    t0, started = time.monotonic(), utc_now()
    out.mkdir(parents=True, exist_ok=True)
    cfg = read_json(config_path)
    digest = source_digest()
    (out / "source").mkdir(exist_ok=True)
    for name in SOURCE_FILES:
        shutil.copyfile(ROOT / "gems3" / name, out / "source" / name)
    shutil.copyfile(config_path, out / "source/config.json")
    folds_all = {*cfg["training_folds"], cfg["tuning_fold"], cfg["audit_fold"]}
    if len(folds_all) != 4 or folds_all != {0, 1, 2, 3}:
        raise ValueError("Training, tuning and audit folds must be disjoint and cover 0-3")
    if cfg["tuning_fold"] == 2 and cfg["audit_fold"] == 3:
        raise ValueError("That role assignment is gapfinder-v2's; this experiment must rotate")
    inputs = inspect_data(data_dir)
    template = data_dir / "sample_submission.tif"
    valid, profile = template_info(template)
    cat = load_catalogues(valid, profile, data_dir)
    known = cat["known"]
    folds, interior = spatial_partition(valid.shape, cfg["block_px"], cfg["buffer_px"],
                                        tuple(cfg["block_origin_px"]))
    train = valid & interior & np.isin(folds, cfg["training_folds"])
    tune = valid & interior & (folds == cfg["tuning_fold"])
    audit = valid & interior & (folds == cfg["audit_fold"])
    matrix, ids, fmeta = build_features(data_dir / "training_features.tif", valid, data_dir / "cache", cfg)
    dist_known = distance_transform_edt(~known).astype("float32")
    sk = skeleton(known)
    tips, dirs = tip_directions(sk, lookback=8)
    tips_ext = {L: extend_tips(tips, dirs, L, valid.shape) & valid & ~known
                for L in cfg["tip_extension_px"] if L}
    contexts = {"gap": MetricContext(cat["sgmc_gap"]), "all": MetricContext(cat["sgmc_all"])}
    known_ctx = MetricContext(known)
    proxies = ["gap", "all", "known"]
    write_json(out / "preregistered.json",
               {"created_at": started, "config": cfg, "config_sha256": sha256(config_path),
                "source_sha256": digest, "inputs": inputs["files"], "feature_cache": fmeta["key"],
                "tips": int(len(tips)),
                "partition": {"block_px": cfg["block_px"], "buffer_px": cfg["buffer_px"],
                              "origin_px": cfg["block_origin_px"],
                              "train": int(train.sum()), "tune": int(tune.sum()), "audit": int(audit.sum())}})
    print(f"partition origin={cfg['block_origin_px']} train={int(train.sum()):,} "
          f"tune={int(tune.sum()):,} audit={int(audit.sum()):,}", flush=True)

    arms, candidates = [], []
    for arm in cfg["arms"]:
        positives = np.zeros_like(known)
        for key in arm["targets"]:
            positives |= cat[key]
        target = kernel_target(positives, ids)
        rows, summary = stratified_rows(target, train.ravel()[ids], cfg, cfg["seed"])
        print(f"\n[{arm['id']}] training on {len(rows):,} rows", flush=True)
        raw, clipped, detail = arm_field(arm, matrix, target, rows, cfg, valid, ids, out, "holdout")
        del target
        ridges = ridge_mask(raw, valid)
        best = None
        for support in cfg["support_targets"]:
            for halo in cfg["halo_px"]:
                for tip in cfg["tip_extension_px"]:
                    p, floor = emission_at(raw, ridges, valid, known, dist_known, tips_ext, support, halo, tip)
                    s = faithful(contexts, p, tune, known)
                    s["known"] = known_proxy(known_ctx, raw, ridges, valid, floor, tune)
                    frac = float(p[tune].sum() / tune.sum())
                    eligible = cfg["min_emitted_fraction"] <= frac <= cfg["max_emitted_fraction"]
                    row = {"arm": arm["id"], "support_target": support, "floor": floor, "halo": halo,
                           "tip": tip, "eligible": bool(eligible), "emitted_fraction": frac,
                           "robust_dti": min(s[k]["dti"] for k in proxies), "tuning": s}
                    candidates.append(row)
                    print(f"  s={support:.4f} f={floor:.4f} h={halo} L={tip} "
                          f"gap={s['gap']['dti']:.4f} all={s['all']['dti']:.4f} known={s['known']['dti']:.4f} "
                          f"support={frac:.3%}", flush=True)
                    if eligible and (best is None or rank(row) < rank(best)):
                        best = row
        arms.append({"arm": arm, "best": best, "clipped_confidence": clipped,
                     "samples": summary, **detail})
        del raw, ridges
        gc.collect()
    eligible = [c for c in candidates if c["eligible"]]
    if not eligible:
        raise ValueError("No eligible candidate")
    selected = sorted(eligible, key=rank)[0]
    wide_pool = [c for c in eligible if c["arm"] == selected["arm"]
                 and c["robust_dti"] >= 0.75 * selected["robust_dti"]]
    wide = max(wide_pool, key=lambda c: (c["emitted_fraction"], c["robust_dti"])) if wide_pool else selected
    frozen = out / "selection-frozen.json"
    write_json(frozen, {"frozen_at": utc_now(), "winner": selected, "wide": wide,
                        "rule": cfg["selection"], "wide_rule": cfg["wide_rule"],
                        "audit_consulted": False, "source_sha256": digest})
    frozen_sha = sha256(frozen)
    print(f"\nFROZEN: {selected['arm']} support={selected['support_target']} h={selected['halo']} "
          f"L={selected['tip']} | wide support={wide['support_target']} h={wide['halo']} L={wide['tip']}",
          flush=True)

    # ---- audit: diagnostic only, cannot change the frozen recipe ----
    raw = np.load(out / f"{selected['arm']}-holdout.npy")
    ridges = ridge_mask(raw, valid)
    marginal = marginal_table(contexts, known_ctx, raw, ridges, valid, known, dist_known, tips_ext, tune,
                              cfg["support_targets"], selected["halo"], selected["tip"])
    audit_rows, comps = [], {}
    for a in arms:
        b = a["best"]
        r = np.load(out / f"{a['arm']['id']}-holdout.npy")
        rg = ridge_mask(r, valid)
        p = emit(r, rg, valid, known, dist_known, tips_ext, b["floor"], b["halo"], b["tip"])
        s = faithful(contexts, p, audit, known)
        s["known"] = known_proxy(known_ctx, r, rg, valid, b["floor"], audit)
        comps[a["arm"]["id"]] = {k: block_components(contexts[k], p, audit, known, cfg["block_px"])
                                 for k in ("gap", "all")}
        audit_rows.append({"arm": a["arm"]["id"], "policy": {k: b[k] for k in
                                                            ("support_target", "floor", "halo", "tip")},
                           "audit": s})
        print(f"AUDIT {a['arm']['id']}: gap={s['gap']['dti']:.4f} all={s['all']['dti']:.4f} "
              f"known={s['known']['dti']:.4f}", flush=True)
        del r, rg, p
    references = {}
    ref_paths = [("gapfinder-v2-fusion", next((ROOT / "docs/downloads").glob("gapfinder-v2-fusion-*.tif"), None)),
                 ("gapfinder-v2-ml", next((ROOT / "docs/downloads").glob("gapfinder-v2-ml-*.tif"), None)),
                 ("riftline-published", next((ROOT / "docs/downloads").glob("riftline-*.tif"), None)),
                 ("legacy-ens12", LEGACY)]
    for label, path in ref_paths:
        if path is None or not Path(path).exists():
            continue
        with rasterio.open(path) as src:
            q = np.where(np.isfinite(src.read(1)) & valid, src.read(1), 0).astype("float32")
        ref_tune, ref_audit = faithful(contexts, q, tune, known), faithful(contexts, q, audit, known)
        ref_tune["known"], ref_audit["known"] = known_ctx.score(q, tune), known_ctx.score(q, audit)
        references[label] = {"file": Path(path).name, "sha256": sha256(path), "tune": ref_tune,
                             "audit": ref_audit,
                             "caveat": "published by an earlier session; scored here on the rotated folds"}
    control = "two-catalogue-regressor"
    bootstrap = {}
    for arm_id in comps:
        if arm_id != control:
            bootstrap[f"{arm_id} vs {control}"] = {
                k: paired_bootstrap(comps[arm_id][k], comps[control][k]) for k in comps[arm_id]}
    if sha256(frozen) != frozen_sha:
        raise RuntimeError("Frozen selection mutated during audit")
    del raw, ridges
    gc.collect()

    # ---- fraction-consistent refit of the frozen arm ----
    arm = next(a for a in cfg["arms"] if a["id"] == selected["arm"])
    positives = np.zeros_like(known)
    for key in arm["targets"]:
        positives |= cat[key]
    target = kernel_target(positives, ids)
    frac = next(a["samples"]["fractions"] for a in arms if a["arm"]["id"] == arm["id"])
    rows, refit_summary = stratified_rows(target, valid.ravel()[ids], cfg, cfg["seed"], fractions=frac)
    print(f"Refit {arm['id']} on {len(rows):,} rows (fraction-consistent)", flush=True)
    raw_refit, refit_clipped, refit_detail = arm_field(arm, matrix, target, rows, cfg, valid, ids,
                                                       out, "refit")
    del target
    raw_hold = np.load(out / f"{arm['id']}-holdout.npy")
    policy = (selected["support_target"], selected["halo"], selected["tip"])
    p_refit, _ = emission_at(raw_refit, ridge_mask(raw_refit, valid), valid, known, dist_known, tips_ext, *policy)
    p_hold, _ = emission_at(raw_hold, ridge_mask(raw_hold, valid), valid, known, dist_known, tips_ext, *policy)
    s_refit, s_hold = float(p_refit[valid].mean()), float(p_hold[valid].mean())
    refit_ok = (cfg["min_emitted_fraction"] <= s_refit <= cfg["max_emitted_fraction"]
                and 1 / 1.5 <= s_refit / max(s_hold, 1e-12) <= 1.5)
    if refit_ok:
        deployed_raw, ml, role = raw_refit, p_refit, "all-fold refit (fraction-consistent sampling)"
    else:
        deployed_raw, ml, role = raw_hold, p_hold, "frozen holdout model (refit rejected by pre-registered gate)"
    deployed_model = (refit_detail["model_file"] if refit_ok
                      else next(a["model_file"] for a in arms if a["arm"]["id"] == selected["arm"]))
    deployment = {"refit_support": s_refit, "holdout_support": s_hold, "refit_accepted": bool(refit_ok),
                  "model_role": role, "model_file": deployed_model,
                  "model_sha256": sha256(out / deployed_model),
                  "policy": dict(zip(("support_target", "halo", "tip"), policy)),
                  "refit_samples": refit_summary, "refit_clipped": refit_clipped}
    del raw_refit, raw_hold, p_refit, p_hold
    gc.collect()

    # ---- portfolio export ----
    sgmc_gap = cat["sgmc_gap"].astype("float32")
    wide_field, wide_floor = emission_at(deployed_raw, ridge_mask(deployed_raw, valid), valid, known,
                                         dist_known, tips_ext, wide["support_target"], wide["halo"],
                                         wide["tip"])
    fields = {"fusion": np.maximum(ml, sgmc_gap), "ml": ml, "wide": wide_field}
    with rasterio.open(LEGACY) as src:
        legacy = np.where(valid, src.read(1), 0)
    rift_path = next((ROOT / "docs/downloads").glob("riftline-*.tif"), None)
    rift = None
    if rift_path is not None:
        with rasterio.open(rift_path) as src:
            rift = np.where(valid, src.read(1), 0)
    gap_path = next((ROOT / "docs/downloads").glob("gapfinder-v2-fusion-*.tif"), None)
    gap_pub = None
    if gap_path is not None:
        with rasterio.open(gap_path) as src:
            gap_pub = np.where(valid, src.read(1), 0)
    short = selected["arm"]
    policy_text = f"s={selected['support_target']:.4f} h={selected['halo']} L={selected['tip']}"
    portfolio = []
    for variant, field in fields.items():
        field = np.where(valid, field, 0).astype("float32")
        tags = {"strategy": cfg["name"], "variant": variant, "arm": selected["arm"],
                "policy": policy_text, "selection_sha256": frozen_sha, "seed": str(cfg["seed"])}
        name, zname, report = export(field, template, out, variant, tags,
                                     f"Coverline {variant}: binary fault-trace prediction at the "
                                     f"metric-derived support point; not calibrated probability",
                                     prefix=cfg["name"])
        idtag = report["sha256"][:10]
        notes = {
            "fusion": f"Coverline v3 fusion | {short} 12-level support sweep {policy_text} "
                      f"+ USGS SGMC-gap traces | {idtag}",
            "ml": f"Coverline v3 ML-only | {short} 12-level support sweep {policy_text} "
                  f"| no SGMC traces | {idtag}",
            "wide": f"Coverline v3 wide | {short} recall probe s={wide['support_target']:.4f} "
                    f"h={wide['halo']} L={wide['tip']} | more coverage, more FP mass | {idtag}",
        }
        diff = {"vs_legacy_ens12": int(np.count_nonzero(field[valid] != legacy[valid]))}
        if rift is not None:
            diff["vs_riftline"] = int(np.count_nonzero(field[valid] != rift[valid]))
        if gap_pub is not None:
            diff["vs_gapfinder_v2_fusion"] = int(np.count_nonzero(field[valid] != gap_pub[valid]))
        portfolio.append({"variant": variant, "file": name, "zip": zname, "sha256": report["sha256"],
                          "bytes": report["bytes"], "note": notes[variant], "validation": report,
                          "emitted_pixels": int((field[valid] > 0).sum()),
                          "emitted_fraction": float((field[valid] > 0).mean()),
                          "on_known_pixels": int((field[known] > 0).sum()),
                          "different_pixels": diff})
        print(f"PASS {name}\n  NOTE: {notes[variant]}", flush=True)
    if source_digest() != digest:
        raise RuntimeError("Source changed during run")
    report = {"schema_version": 1, "name": "Coverline", "strategy": cfg["name"], "started_at": started,
              "completed_at": utc_now(), "seconds": round(time.monotonic() - t0, 1),
              "status": "format-validated portfolio; unsubmitted; competition scores unknown",
              "competition_scores": {v["variant"]: None for v in portfolio},
              "config": cfg, "config_sha256": sha256(config_path), "source_sha256": digest,
              "environment": {"python": platform.python_version(), "numpy": np.__version__,
                              "sklearn": sklearn.__version__, "rasterio": rasterio.__version__,
                              "compute": "CPU, 2 threads, no GPU"},
              "inputs": inputs["files"], "sgmc_raster_sha256": sha256(PROXY),
              "catalogue_pixels": {k: int(v.sum()) for k, v in cat.items()},
              "tips_used": int(len(tips)),
              "partition": {"training_folds": cfg["training_folds"], "tuning_fold": cfg["tuning_fold"],
                            "audit_fold": cfg["audit_fold"], "buffer_px": cfg["buffer_px"],
                            "origin_px": cfg["block_origin_px"], "train_pixels": int(train.sum()),
                            "tune_pixels": int(tune.sum()), "audit_pixels": int(audit.sum())},
              "metric_algebra": {
                  "pixel_denominator_cost": 0.2,
                  "break_even_credit_per_pixel_at_leader": float(0.2 * 0.3049),
                  "note": "Exact for binary p=1 emission; see the module docstring for the derivation."},
              "arms": arms, "candidates": candidates, "selected": selected, "wide": wide,
              "selection_frozen_sha256": frozen_sha, "marginal_value_tuning": marginal,
              "audit": audit_rows, "audit_bootstrap": bootstrap, "references": references,
              "deployment": deployment, "portfolio": portfolio, "wide_floor": wide_floor,
              "limitations": [
                  "Local truth is the public SGMC layer and the supplied labels, never the hidden expert labels.",
                  "The partition is a half-block rotation of v2's lattice; fold 2 here overlaps v2 regions.",
                  "SGMC traces inside the fusion file cannot be scored locally without circularity.",
                  "Binary emission is a deliberate choice justified by the metric algebra, not a calibrated probability.",
                  "No 1 m DEM, no GPU, no hidden labels, no authenticated upload."]}
    write_json(out / "experiment.json", report)
    print(f"\nDone in {report['seconds']} s. No competition score has been measured.", flush=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/coverage-v3.json")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    output = args.output or ROOT / "outputs" / read_json(args.config)["name"]
    run(args.config, args.data, output)


if __name__ == "__main__":
    main()
