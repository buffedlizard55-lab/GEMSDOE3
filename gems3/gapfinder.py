"""Gapfinder v1: predict the faults the supplied catalogue does NOT contain.

Why this differs from Riftline and the legacy ensemble
------------------------------------------------------
Official DrivenData staff answers (retrieved 2026-09-25, links in configs/gapfinder.json):
  1. Known USGS/INGENIOUS fault pixels are masked from scoring; the mask is pixel-exact and
     identical to labels.tif. Predictions *on* them are free, predictions *next to* them are
     fully penalised unless a new fault is nearby.
  2. "New fault" = any fault pixel not already captured, including continuations/splays.
So the local objective must (a) exclude known pixels from both truth and penalty, and (b) use a
truth set that is *not* the supplied catalogue. The only public stand-in is the independent USGS
State Geologic Map Compilation (SGMC) fault layer, restricted to pixels not on known faults.

Honesty constraints
-------------------
* Train/tune/audit are distinct spatial folds with a 48 px buffer. SGMC appears as a training
  target only inside training folds; tuning/audit SGMC is evaluation-only.
* The recipe is frozen (hash recorded) before any audit-fold statistic is computed.
* Adding SGMC traces *directly* to a submission cannot be evaluated locally without circularity,
  so it is published as a separate, explicitly labelled leaderboard experiment.
* Nothing here is a hidden-label or leaderboard score.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import platform
import shutil
import time
import zipfile
from pathlib import Path

import joblib
import numpy as np
import rasterio
import sklearn
from scipy.ndimage import distance_transform_edt
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .common import ROOT, read_json, sha256, utc_now, write_json
from .data import inspect_data
from .emission import ridge_mask
from .features import build_features, spatial_partition
from .geometry import extend_tips, skeleton, tip_directions
from .metric import MetricContext
from .raster import template_info, write_submission

SOURCES = ["common.py", "data.py", "emission.py", "features.py", "geometry.py", "metric.py",
           "raster.py", "gapfinder.py"]
PROXY = ROOT / "legacy/data/evidence/proxy/proxy_catalogue.tif"
PROXY_META = ROOT / "legacy/data/evidence/proxy/proxy_stats.json"
LEGACY = ROOT / "legacy/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif"


def source_digest() -> str:
    h = hashlib.sha256()
    for name in SOURCES:
        h.update(name.encode())
        h.update((ROOT / "gems3" / name).read_bytes())
    return h.hexdigest()


def load_catalogues(valid: np.ndarray, profile: dict, data_dir: Path):
    with rasterio.open(data_dir / "labels.tif") as src:
        known = (src.read(1) == 1) & valid
    if sha256(PROXY) != read_json(PROXY_META)["output"]["sha256"]:
        raise ValueError("Pinned SGMC raster changed; provenance review required")
    with rasterio.open(PROXY) as src:
        if src.shape != valid.shape or src.crs != profile["crs"] or src.transform != profile["transform"]:
            raise ValueError("SGMC raster is not on the exact competition grid")
        code = src.read(1)
    sgmc_any = (code > 0) & valid
    return {"known": known,
            "sgmc": sgmc_any,                       # every SGMC fault pixel (training target use)
            "sgmc_gap": (code == 2) & valid,        # >= 3.2 px from any known pixel
            "sgmc_all": sgmc_any & ~known}          # every SGMC pixel not exactly on a known pixel


def kernel_target(positives: np.ndarray, ids: np.ndarray) -> np.ndarray:
    d = distance_transform_edt(~positives)
    return np.maximum(1 - d.ravel()[ids] / 3, 0).astype("float32")


def stratified_rows(target: np.ndarray, allowed: np.ndarray, config: dict, seed: int, fractions=None):
    """Keep all exact positives; sample near/unlabeled strata. With `fractions`, reuse the holdout
    model's inclusion fractions so the class mixture is unchanged when the region grows."""
    rng = np.random.default_rng(seed)
    exact = np.flatnonzero(allowed & (target == 1))
    near = np.flatnonzero(allowed & (target > 0) & (target < 1))
    unl = np.flatnonzero(allowed & (target == 0))
    if not exact.size or not unl.size:
        raise ValueError("Split needs positives and unlabeled rows")
    if fractions is None:
        n_near, n_unl = min(len(near), config["max_near_samples"]), min(len(unl), config["max_unlabeled_samples"])
    else:
        n_near = min(len(near), int(round(fractions["near"] * len(near))))
        n_unl = min(len(unl), int(round(fractions["unlabeled"] * len(unl))))
    near = rng.choice(near, n_near, replace=False)
    unl_s = rng.choice(unl, n_unl, replace=False)
    rows = np.concatenate([exact, near, unl_s])
    rng.shuffle(rows)
    avail_near = int((allowed & (target > 0) & (target < 1)).sum())
    summary = {"exact_positive": int(len(exact)), "near_positive": int(n_near), "unlabeled": int(n_unl),
               "available_near": avail_near, "available_unlabeled": int(len(unl)),
               "fractions": {"near": n_near / max(avail_near, 1), "unlabeled": n_unl / len(unl)},
               "positive_share": float((len(exact) + n_near) / len(rows)),
               "sample_indices_sha256": hashlib.sha256(rows.tobytes()).hexdigest()}
    return rows, summary


def fit(matrix, target, rows, config):
    model = HistGradientBoostingRegressor(loss="squared_error", random_state=config["seed"], **config["model"])
    x = np.array(matrix[rows], dtype="float32", copy=True)
    with threadpool_limits(limits=2):
        model.fit(x, target[rows])
    del x
    return model


def predict(model, matrix, ids, shape):
    out = np.zeros(int(np.prod(shape)), dtype="float32")
    clipped = 0
    with threadpool_limits(limits=2):
        for start in range(0, len(ids), 65536):
            stop = min(start + 65536, len(ids))
            v = model.predict(np.asarray(matrix[start:stop]))
            if not np.isfinite(v).all():
                raise ValueError("Nonfinite model output")
            clipped += int(((v < 0) | (v > 1)).sum())
            out[ids[start:stop]] = np.clip(v, 0, 1)  # bounded link, logged; exporter never clips
    return out.reshape(shape), clipped


def emit(raw, ridges, valid, known, dist_known, tips_ext, floor, halo, tip_px):
    keep = valid & ridges & (raw >= floor)
    if halo:
        keep &= ~((dist_known > 0) & (dist_known <= halo))
    if tip_px:
        keep |= tips_ext[tip_px]
    keep &= valid & ~known  # known pixels are masked by the organisers; emit exact zeros there
    return keep.astype("float32")


def faithful(contexts, p, region, known):
    mask = region & ~known
    return {k: ctx.score(p, mask) for k, ctx in contexts.items()}


def known_proxy(known_ctx, raw, ridges, valid, floor, region):
    """Held-out SUPPLIED faults as a stand-in for unseen Qfault-type faults. Known pixels must be
    emit-able here (they are the truth), so the organiser mask and halo are not applied.

    Tip-extension rays are deliberately EXCLUDED: they are constructed from the known traces and
    start one pixel beyond each tip, so they would collect kernel credit from the very truth pixels
    that generated them (a leak found during the first v2 attempt; see evidence/gapfinder-v2-aborted.txt).
    """
    keep = valid & ridges & (raw >= floor)
    return known_ctx.score(keep.astype("float32"), region)


def block_components(context, p, region, known, block):
    rows = []
    h, w = region.shape
    for r in range(0, h, block):
        for c in range(0, w, block):
            m = np.zeros_like(region)
            m[r:r + block, c:c + block] = region[r:r + block, c:c + block]
            m &= ~known
            if m.any():
                s = context.score(p, m)
                rows.append((s["TP_w"], s["FP_w"], s["FN_w"]))
    return np.asarray(rows, dtype="float64")


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n: int = 2000, seed: int = 7) -> dict:
    """Block bootstrap of the GLOBAL ratio for two candidates on identical block draws."""
    rng = np.random.default_rng(seed)

    def dti(x):
        tp, fp, fn = x.sum(axis=0)
        return tp / (tp + 0.2 * fp + 0.8 * fn + 1e-7)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = rng.integers(0, k, k)
        diffs.append(dti(a[idx]) - dti(b[idx]))
    diffs = np.asarray(diffs)
    return {"blocks": int(k), "observed_difference": float(dti(a) - dti(b)),
            "ci95": [float(np.quantile(diffs, .025)), float(np.quantile(diffs, .975))],
            "p_a_better": float(np.mean(diffs > 0)), "draws": n}


def export(field, template, out_dir, variant, tags, description, prefix="gapfinder"):
    stamp = utc_now().replace("-", "").replace(":", "")
    staged = out_dir / f"{variant}.pending-name.tif"
    report = write_submission(field, template, staged, tags=tags, description=description)
    name = f"{prefix}-{variant}-{stamp}-{report['sha256'][:10]}.tif"
    staged.rename(out_dir / name)
    report["file"] = name
    zpath = out_dir / name.replace(".tif", ".zip")
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, (out_dir / name).read_bytes())
    with zipfile.ZipFile(zpath) as z:
        if z.namelist() != [name] or hashlib.sha256(z.read(name)).hexdigest() != report["sha256"]:
            raise ValueError("ZIP must contain exactly the validated GeoTIFF")
    return name, zpath.name, report


def run(config_path: Path, data_dir: Path, out: Path) -> dict:
    t0, started = time.monotonic(), utc_now()
    out.mkdir(parents=True, exist_ok=True)
    cfg = read_json(config_path)
    digest = source_digest()
    (out / "source").mkdir(exist_ok=True)
    for name in SOURCES:
        shutil.copyfile(ROOT / "gems3" / name, out / "source" / name)
    shutil.copyfile(config_path, out / "source/config.json")
    folds_all = {*cfg["training_folds"], cfg["tuning_fold"], cfg["audit_fold"]}
    if len(folds_all) != 4 or folds_all != {0, 1, 2, 3}:
        raise ValueError("Training, tuning and audit folds must be disjoint and cover 0-3")
    inputs = inspect_data(data_dir)
    template = data_dir / "sample_submission.tif"
    valid, profile = template_info(template)
    cat = load_catalogues(valid, profile, data_dir)
    known = cat["known"]
    folds, interior = spatial_partition(valid.shape, cfg["block_px"], cfg["buffer_px"])
    train = valid & interior & np.isin(folds, cfg["training_folds"])
    tune = valid & interior & (folds == cfg["tuning_fold"])
    audit = valid & interior & (folds == cfg["audit_fold"])
    matrix, ids, fmeta = build_features(data_dir / "training_features.tif", valid, data_dir / "cache", cfg)
    dist_known = distance_transform_edt(~known).astype("float32")
    sk = skeleton(known)
    tips, dirs = tip_directions(sk, lookback=8)
    tips_ext = {L: extend_tips(tips, dirs, L, valid.shape) & valid & ~known for L in cfg["tip_extension_px"] if L}
    contexts = {"gap": MetricContext(cat["sgmc_gap"]), "all": MetricContext(cat["sgmc_all"])}
    selection_proxies = cfg.get("selection_proxies", ["gap", "all"])
    if not set(selection_proxies) <= {"gap", "all", "known"} or not {"gap", "all"} & set(selection_proxies):
        raise ValueError("Unsupported selection proxies")
    known_ctx = MetricContext(known) if "known" in selection_proxies else None

    def rank(c):
        """Pre-registered order: robust DTI, then lower prediction mass, then arm/floor/halo/tip."""
        return (-c["robust_dti"], c["tuning"]["gap"]["prediction_mass"], c["arm"], c["floor"], c["halo"], c["tip"])
    write_json(out / "preregistered.json", {"created_at": started, "config": cfg, "config_sha256": sha256(config_path),
               "source_sha256": digest, "inputs": inputs["files"], "feature_cache": fmeta["key"],
               "tips": int(len(tips)), "partition_pixels": {"train": int(train.sum()), "tune": int(tune.sum()),
                                                             "audit": int(audit.sum())}})
    arms, candidates, holdout_samples = [], [], {}
    for arm in cfg["arms"]:
        positives = np.zeros_like(known)
        for key in arm["positives"]:
            positives |= cat[key]
        target = kernel_target(positives, ids)
        rows, summary = stratified_rows(target, train.ravel()[ids], cfg, cfg["seed"])
        holdout_samples[arm["id"]] = summary
        print(f"\n[{arm['id']}] training on {len(rows):,} rows", flush=True)
        ta = time.monotonic()
        model = fit(matrix, target, rows, cfg)
        joblib.dump(model, out / f"{arm['id']}.joblib", compress=3)
        raw, clipped = predict(model, matrix, ids, valid.shape)
        del model, target
        np.save(out / f"{arm['id']}-holdout.npy", raw)
        ridges = ridge_mask(raw, valid)
        best = None
        for floor in cfg["floors"]:
            for halo in cfg["halo_px"]:
                for tip in cfg["tip_extension_px"]:
                    p = emit(raw, ridges, valid, known, dist_known, tips_ext, floor, halo, tip)
                    s = faithful(contexts, p, tune, known)
                    if known_ctx is not None:
                        s["known"] = known_proxy(known_ctx, raw, ridges, valid, floor, tune)
                    frac = float(p[tune].sum() / tune.sum())
                    ok = cfg["min_emitted_fraction"] <= frac <= cfg["max_emitted_fraction"]
                    row = {"arm": arm["id"], "floor": floor, "halo": halo, "tip": tip, "eligible": ok,
                           "emitted_fraction": frac, "robust_dti": min(s[k]["dti"] for k in selection_proxies),
                           "tuning": s}
                    candidates.append(row)
                    extra = f" known={s['known']['dti']:.4f}" if "known" in s else ""
                    print(f"  f={floor:.2f} h={halo} L={tip}  gap={s['gap']['dti']:.4f} all={s['all']['dti']:.4f}"
                          f"{extra} support={frac:.3%}", flush=True)
                    if ok and (best is None or rank(row) < rank(best)):
                        best = row  # same ordering as the global selection, so ties resolve identically
        arms.append({"arm": arm, "best": best, "clipped": clipped, "seconds": round(time.monotonic() - ta, 1),
                     "samples": summary})
        del raw, ridges
        gc.collect()
    eligible = [c for c in candidates if c["eligible"]]
    if not eligible:
        raise ValueError("No eligible candidate")
    selected = sorted(eligible, key=rank)[0]
    if not any(a["best"] is selected for a in arms):
        raise AssertionError("Per-arm best must include the globally selected policy (it is the one audited)")
    frozen = out / "selection-frozen.json"
    write_json(frozen, {"frozen_at": utc_now(), "winner": selected, "rule": cfg["selection"],
                        "audit_consulted": False, "source_sha256": digest})
    frozen_sha = sha256(frozen)
    print(f"\nFROZEN: {selected['arm']} f={selected['floor']} h={selected['halo']} L={selected['tip']}", flush=True)

    # ---- audit (diagnostic only; cannot change the frozen recipe) ----
    audit_rows, comps = [], {}
    for a in arms:
        b = a["best"]
        raw = np.load(out / f"{a['arm']['id']}-holdout.npy")
        p = emit(raw, ridge_mask(raw, valid), valid, known, dist_known, tips_ext, b["floor"], b["halo"], b["tip"])
        s = faithful(contexts, p, audit, known)
        if known_ctx is not None:
            s["known"] = known_proxy(known_ctx, raw, ridge_mask(raw, valid), valid, b["floor"], audit)
        comps[a["arm"]["id"]] = {k: block_components(contexts[k], p, audit, known, cfg["block_px"]) for k in contexts}
        audit_rows.append({"arm": a["arm"]["id"], "policy": {k: b[k] for k in ("floor", "halo", "tip")}, "audit": s})
        extra = f" known={s['known']['dti']:.4f}" if "known" in s else ""
        print(f"AUDIT {a['arm']['id']}: gap={s['gap']['dti']:.4f} all={s['all']['dti']:.4f}{extra}", flush=True)
        del raw, p
    references = {}
    for label, path in (("riftline-published", next((ROOT / "docs/downloads").glob("riftline-*.tif"), None)),
                        ("legacy-ens12", LEGACY)):
        if path is None:
            continue
        with rasterio.open(path) as src:
            q = src.read(1)
        q = np.where(np.isfinite(q) & valid, q, 0).astype("float32")
        ref_tune, ref_audit = faithful(contexts, q, tune, known), faithful(contexts, q, audit, known)
        if known_ctx is not None:
            ref_tune["known"], ref_audit["known"] = known_ctx.score(q, tune), known_ctx.score(q, audit)
        references[label] = {"file": path.name, "sha256": sha256(path), "tune": ref_tune, "audit": ref_audit,
                             "caveat": ("Riftline was trained on folds 2-3, so these folds are IN-SAMPLE for it"
                                        if label.startswith("riftline") else
                                        "Legacy training regions unknown here; likely the artifact behind extradr19's 0.1563, unproven")}
    control = "qfault-target"
    bootstrap = {}
    for arm_id in comps:
        if arm_id != control:
            bootstrap[f"{arm_id} vs {control}"] = {k: paired_bootstrap(comps[arm_id][k], comps[control][k])
                                                   for k in contexts}
    if sha256(frozen) != frozen_sha:
        raise RuntimeError("Frozen selection mutated during audit")

    # ---- fraction-consistent refit of the frozen arm ----
    arm = next(a for a in cfg["arms"] if a["id"] == selected["arm"])
    positives = np.zeros_like(known)
    for key in arm["positives"]:
        positives |= cat[key]
    target = kernel_target(positives, ids)
    frac = holdout_samples[arm["id"]]["fractions"]
    rows, refit_summary = stratified_rows(target, valid.ravel()[ids], cfg, cfg["seed"], fractions=frac)
    print(f"Refit {arm['id']} on {len(rows):,} rows (fraction-consistent)", flush=True)
    model = fit(matrix, target, rows, cfg)
    del target
    joblib.dump(model, out / "refit-model.joblib", compress=3)
    raw_refit, refit_clipped = predict(model, matrix, ids, valid.shape)
    del model
    raw_hold = np.load(out / f"{arm['id']}-holdout.npy")
    pol = (selected["floor"], selected["halo"], selected["tip"])
    p_refit = emit(raw_refit, ridge_mask(raw_refit, valid), valid, known, dist_known, tips_ext, *pol)
    p_hold = emit(raw_hold, ridge_mask(raw_hold, valid), valid, known, dist_known, tips_ext, *pol)
    s_refit, s_hold = float(p_refit[valid].mean()), float(p_hold[valid].mean())
    refit_ok = (cfg["min_emitted_fraction"] <= s_refit <= cfg["max_emitted_fraction"]
                and 1 / 1.5 <= s_refit / max(s_hold, 1e-12) <= 1.5)
    if refit_ok:
        ml, role, model_file = p_refit, "all-fold refit (fraction-consistent sampling)", "refit-model.joblib"
        np.save(out / "final-confidence.npy", raw_refit)
    else:
        ml, role, model_file = p_hold, "frozen holdout model (refit rejected by pre-registered gate)", f"{arm['id']}.joblib"
        np.save(out / "final-confidence.npy", raw_hold)
    deployment = {"refit_support": s_refit, "holdout_support": s_hold, "refit_accepted": bool(refit_ok),
                  "model_role": role, "model_file": model_file, "model_sha256": sha256(out / model_file),
                  "refit_samples": refit_summary, "refit_clipped": refit_clipped}
    del raw_refit, raw_hold, p_refit, p_hold
    gc.collect()
    if source_digest() != digest:
        raise RuntimeError("Source changed during run")

    # ---- portfolio export ----
    sgmc_gap = cat["sgmc_gap"].astype("float32")
    fusion = np.maximum(ml, sgmc_gap)
    fields = {"fusion": fusion, "ml": ml, "sgmc-gap": sgmc_gap}
    with rasterio.open(LEGACY) as src:
        legacy = np.where(valid, src.read(1), 0)
    rift_path = next((ROOT / "docs/downloads").glob("riftline-*.tif"), None)
    rift = None
    if rift_path is not None:
        with rasterio.open(rift_path) as src:
            rift = np.where(valid, src.read(1), 0)
    portfolio = []
    short = selected["arm"].replace("-target", "")
    policy = f"f={selected['floor']} h={selected['halo']} L={selected['tip']}"
    for variant, field in fields.items():
        field = np.where(valid, field, 0).astype("float32")
        tags = {"strategy": cfg["name"], "variant": variant, "arm": selected["arm"], "policy": policy,
                "selection_sha256": frozen_sha, "seed": str(cfg["seed"])}
        name, zname, report = export(field, template, out, variant, tags,
                                     f"Gapfinder {variant}: binary fault-trace prediction; not calibrated probability",
                                     prefix=cfg["name"])
        idtag = report["sha256"][:10]
        ver = cfg["name"].split("-")[-1]
        notes = {"fusion": f"Gapfinder {ver} fusion | {short} HGB ridge {policy} + SGMC-gap traces | {idtag}",
                 "ml": f"Gapfinder {ver} ML-only | {short} HGB ridge {policy} | no SGMC traces | {idtag}",
                 "sgmc-gap": f"Gapfinder {ver} SGMC-gap only | USGS SGMC faults >300m from labels | no model | {idtag}"}
        diff = {"vs_legacy_ens12": int(np.count_nonzero(field[valid] != legacy[valid]))}
        if rift is not None:
            diff["vs_riftline"] = int(np.count_nonzero(field[valid] != rift[valid]))
        portfolio.append({"variant": variant, "file": name, "zip": zname, "sha256": report["sha256"],
                          "bytes": report["bytes"], "note": notes[variant], "validation": report,
                          "emitted_pixels": int((field[valid] > 0).sum()),
                          "emitted_fraction": float((field[valid] > 0).mean()),
                          "on_known_pixels": int((field[known] > 0).sum()),
                          "different_pixels": diff})
        print(f"PASS {name}\n  NOTE: {notes[variant]}", flush=True)
    report = {"schema_version": 1, "name": "Gapfinder", "strategy": cfg["name"], "started_at": started,
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
                            "train_pixels": int(train.sum()), "tune_pixels": int(tune.sum()),
                            "audit_pixels": int(audit.sum())},
              "arms": arms, "candidates": candidates, "selected": selected, "selection_frozen_sha256": frozen_sha,
              "audit": audit_rows, "audit_bootstrap": bootstrap, "references": references,
              "deployment": deployment, "portfolio": portfolio,
              "limitations": [
                  "Local truth is the public SGMC fault layer (~1:1,000,000 compilation), not the hidden expert labels.",
                  "SGMC-direct traces cannot be scored locally without circularity; fusion vs ml is a leaderboard experiment.",
                  "One rotated split (tune fold 2, audit fold 3); block bootstrap measures spatial sampling noise only.",
                  "Tip extensions are geometric hypotheses; truncation self-tests do not prove real continuations.",
                  "No 1 m DEM, no GPU, no hidden labels, no authenticated upload."]}
    write_json(out / "experiment.json", report)
    print(f"\nDone in {report['seconds']} s. No competition score has been measured.", flush=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/gapfinder-v2.json")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    output = args.output or ROOT / "outputs" / read_json(args.config)["name"]
    run(args.config, args.data, output)


if __name__ == "__main__":
    main()
