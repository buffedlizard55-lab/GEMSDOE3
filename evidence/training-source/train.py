"""CPU experiment: distance-field regression + multiscale context + cautious unlabeled weights.

Not a statistically unbiased PU-risk estimator: missingness is spatially biased and the class
prior is unknown. Confidence outputs are not calibrated probabilities. Selection uses published
catalogues on tuning fold 0; fold 1 is read only after the winning recipe has been frozen.
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
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .common import ROOT, code_digest, read_json, sha256, utc_now, write_json
from .data import inspect_data
from .emission import emit, ridge_mask
from .features import build_features, spatial_partition
from .metric import MetricContext
from .raster import template_info, write_submission


def sample_rows(target: np.ndarray, allowed: np.ndarray, config: dict, seed: int):
    """Retain known positives; stratify near positives and unlabeled; never call zeros true negatives."""
    rng = np.random.default_rng(seed)
    exact = np.flatnonzero(allowed & (target == 1))
    near = np.flatnonzero(allowed & (target > 0) & (target < 1))
    unlabeled = np.flatnonzero(allowed & (target == 0))
    if not exact.size or not unlabeled.size:
        raise ValueError("Training split needs both known positives and unlabeled examples")
    near = rng.choice(near, min(len(near), config["max_near_samples"]), replace=False)
    unlabeled = rng.choice(unlabeled, min(len(unlabeled), config["max_unlabeled_samples"]), replace=False)
    rows = np.concatenate([exact, near, unlabeled])
    rng.shuffle(rows)
    return rows, {"exact_positive": len(exact), "near_positive": len(near), "unlabeled": len(unlabeled),
                  "sample_indices_sha256": hashlib.sha256(rows.tobytes()).hexdigest()}


def fit_arm(matrix, target, sample, arm, config):
    columns = matrix.shape[1] if arm["context"] else 19
    model = HistGradientBoostingRegressor(loss="squared_error", random_state=config["seed"], **config["model"])
    y = target[sample]
    weights = np.where(y > 0, 1.0, arm["unlabeled_weight"]).astype("float32")
    x = np.array(matrix[sample, :columns], dtype="float32", copy=True)
    with threadpool_limits(limits=2):
        model.fit(x, y, sample_weight=weights)
    return model


def predict_grid(model, matrix, ids, shape, arm):
    columns = matrix.shape[1] if arm["context"] else 19
    result = np.zeros(int(np.prod(shape)), dtype="float32")
    clip_count = 0
    with threadpool_limits(limits=2):
        for start in range(0, len(ids), 65536):
            stop = min(start + 65536, len(ids))
            values = model.predict(np.asarray(matrix[start:stop, :columns]))
            if not np.isfinite(values).all():
                raise ValueError("Model returned nonfinite confidence; pipeline stopped")
            clip_count += int(((values < 0) | (values > 1)).sum())
            # Squared-error regressors are unbounded; bounded link is part of the model recipe,
            # applied before evaluation as well as export. Exporter itself never fixes bad input.
            result[ids[start:stop]] = np.clip(values, 0, 1).astype("float32")
    return result.reshape(shape), clip_count


def choose_candidate(candidates: list[dict]) -> dict:
    eligible = [c for c in candidates if c["eligible"] and c["tuning"]["dti"] is not None]
    if not eligible:
        raise ValueError("No nondegenerate candidate passed the pre-registered support limits")
    return sorted(eligible, key=lambda c: (-c["tuning"]["dti"], c["tuning"]["prediction_mass"],
                                          c["arm"], c["floor"], c["emission"]))[0]


def run(config_path: Path, data_dir: Path, output_dir: Path) -> dict:
    started, start_time = utc_now(), time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = read_json(config_path)
    if config["tuning_fold"] == config["audit_fold"] or not {config["tuning_fold"], config["audit_fold"]} <= set(range(4)):
        raise ValueError("Tuning and audit need distinct valid folds")
    if not (0 <= config["min_emitted_fraction"] < config["max_emitted_fraction"] < 1):
        raise ValueError("Invalid nondegeneracy limits")
    if any(a["unlabeled_weight"] <= 0 or a["unlabeled_weight"] > 1 for a in config["arms"]):
        raise ValueError("Unlabeled weights must be in (0,1]")
    input_report = inspect_data(data_dir)
    template = data_dir / "sample_submission.tif"
    valid, profile = template_info(template)
    with rasterio.open(data_dir / "labels.tif") as src:
        known = (src.read(1) == 1) & valid
    proxy_path = ROOT / "legacy/data/evidence/proxy/proxy_catalogue.tif"
    proxy_meta = read_json(ROOT / "legacy/data/evidence/proxy/proxy_stats.json")
    if sha256(proxy_path) != proxy_meta["output"]["sha256"]:
        raise ValueError("Inherited proxy changed; source review required before use")
    with rasterio.open(proxy_path) as src:
        if src.shape != valid.shape or src.crs != profile["crs"] or src.transform != profile["transform"]:
            raise ValueError("Proxy must match the exact competition grid")
        proxy = (src.read(1) == 2) & valid
    folds, interior = spatial_partition(valid.shape, config["block_px"], config["buffer_px"])
    tune_mask = valid & interior & (folds == config["tuning_fold"])
    audit_mask = valid & interior & (folds == config["audit_fold"])
    train_mask = valid & interior & ~np.isin(folds, [config["tuning_fold"], config["audit_fold"]])
    if not all(np.any(known & mask) for mask in [train_mask, tune_mask, audit_mask]):
        raise ValueError("A spatial partition has no known faults")
    matrix, ids, feature_meta = build_features(data_dir / "training_features.tif", valid,
                                              data_dir / "cache", config)
    # This target uses only PROVIDED known labels. Proxy labels are never fitted.
    distances = distance_transform_edt(~known)
    target = np.maximum(1 - distances.ravel()[ids] / 3, 0).astype("float32")
    del distances
    samples, sample_summary = sample_rows(target, train_mask.ravel()[ids], config, config["seed"])
    context = MetricContext(known | proxy)
    candidates, arms = [], []
    fingerprint = code_digest()
    write_json(output_dir / "preregistered.json", {"created_at": started, "config": config,
               "config_sha256": sha256(config_path), "code_sha256": fingerprint,
               "feature_cache": feature_meta, "inputs": input_report["files"],
               "train_samples": sample_summary})
    for arm in config["arms"]:
        print(f"\nTraining {arm['id']} on {len(samples):,} samples", flush=True)
        arm_start = time.monotonic()
        model = fit_arm(matrix, target, samples, arm, config)
        joblib.dump(model, output_dir / f"{arm['id']}.joblib", compress=3)
        raw, n_clipped = predict_grid(model, matrix, ids, valid.shape, arm)
        np.save(output_dir / f"{arm['id']}-holdout.npy", raw)
        del model
        ridges = ridge_mask(raw, valid)
        rows = []
        for floor in config["floors"]:
            for emission in config["emissions"]:
                p = emit(raw, valid, floor, emission, ridges)
                measurement = context.score(p, tune_mask)
                fraction = measurement["prediction_pixels"] / int(tune_mask.sum())
                eligible = config["min_emitted_fraction"] <= fraction <= config["max_emitted_fraction"]
                row = {"arm": arm["id"], "floor": floor, "emission": emission,
                       "eligible": eligible, "emitted_fraction": fraction, "tuning": measurement}
                candidates.append(row)
                rows.append(row)
                print(f" {floor:.2f} {emission:12s} tune union DTI={measurement['dti']:.5f} "
                      f"support={fraction:.3%} eligible={eligible}", flush=True)
        best = choose_candidate(rows)
        arms.append({"arm": arm, "best_tuning_policy": best, "bounded_link_clipped_pixels": n_clipped,
                     "seconds": round(time.monotonic() - arm_start, 3)})
        del raw, ridges, p
        gc.collect()
    selected = choose_candidate(candidates)
    # Persist the selection BEFORE querying any audit-label statistic.
    selection_path = output_dir / "selection-frozen.json"
    write_json(selection_path, {"frozen_at": utc_now(), "winner": selected,
                               "rule": config["selection"], "audit_consulted": False})
    selection_sha = sha256(selection_path)
    print(f"\nFrozen recipe: {selected['arm']} / {selected['emission']} / floor {selected['floor']}", flush=True)
    # Score only each arm's tuning-chosen policy; do not change selection using these results.
    known_context, proxy_context = MetricContext(known), MetricContext(proxy)
    for row in arms:
        best = row["best_tuning_policy"]
        raw = np.load(output_dir / f"{row['arm']['id']}-holdout.npy", mmap_mode="r")
        p = emit(raw, valid, best["floor"], best["emission"])
        row["audit"] = {"known": known_context.score(p, audit_mask),
                        "proxy_only": proxy_context.score(p, audit_mask),
                        "union": context.score(p, audit_mask)}
        print(f"AUDIT {row['arm']['id']}: union={row['audit']['union']['dti']:.5f}; "
              "not used for selection", flush=True)
        if row["arm"]["id"] == selected["arm"]:
            selected_audit = row["audit"]
            audit_blocks = []
            block = config["block_px"]
            for r in range(0, valid.shape[0], block):
                for c in range(0, valid.shape[1], block):
                    mask = np.zeros(valid.shape, bool)
                    mask[r:r+block, c:c+block] = audit_mask[r:r+block, c:c+block]
                    if mask.any():
                        measurement = context.score(p, mask)
                        audit_blocks.append({"row": r, "col": c, **measurement})
        del p, raw
    if sha256(selection_path) != selection_sha:
        raise RuntimeError("Frozen recipe mutated while scoring audit")
    del context, known_context, proxy_context
    gc.collect()
    winning_arm = next(a for a in config["arms"] if a["id"] == selected["arm"])
    all_samples, refit_samples = sample_rows(target, np.ones(len(ids), bool), config, config["seed"])
    print(f"Refitting frozen arm on {len(all_samples):,} samples from all known-label regions", flush=True)
    final_model = fit_arm(matrix, target, all_samples, winning_arm, config)
    refit_model_path = output_dir / "full-refit-model.joblib"
    model_path = output_dir / "final-model.joblib"
    joblib.dump(final_model, refit_model_path, compress=3)
    raw, refit_clipped = predict_grid(final_model, matrix, ids, valid.shape, winning_arm)
    del final_model
    np.save(output_dir / "full-refit-confidence.npy", raw)
    p = emit(raw, valid, selected["floor"], selected["emission"])
    refit_support = float(np.mean(p[valid] > 0))
    refit_eligible = config["min_emitted_fraction"] <= refit_support <= config["max_emitted_fraction"]
    deployment = {"refit_attempted": True, "refit_support_fraction": refit_support,
                  "refit_passed_support_gate": refit_eligible, "refit_bounded_link_clipped_pixels": refit_clipped,
                  "refit_model_sha256": sha256(refit_model_path),
                  "decision_basis": "Unlabeled prediction density only; no audit-label reselection",
                  "policy_revision": config.get("deployment_policy_revision")}
    if refit_eligible:
        shutil.copyfile(refit_model_path, model_path)
        final_clipped = refit_clipped
        deployment["model_role"] = "all-data refit"
    else:
        # Never relax support limits or tune thresholds on audit labels after refit drift.
        # The fallback is the exact unchanged model/policy already selected on tuning data.
        print(f"Refit rejected: support {refit_support:.3%}. Checking unchanged audited model.", flush=True)
        shutil.copyfile(output_dir / f"{selected['arm']}.joblib", model_path)
        raw = np.load(output_dir / f"{selected['arm']}-holdout.npy")
        p = emit(raw, valid, selected["floor"], selected["emission"])
        final_clipped = next(a["bounded_link_clipped_pixels"] for a in arms if a["arm"]["id"] == selected["arm"])
        deployment["model_role"] = "frozen spatial-holdout model; full refit rejected"
    support = float(np.mean(p[valid] > 0))
    deployment["published_support_fraction"] = support
    if not config["min_emitted_fraction"] <= support <= config["max_emitted_fraction"]:
        raise ValueError("Neither refit nor unchanged selected model passes the global support gate")
    np.save(output_dir / "final-confidence.npy", raw)
    timestamp = utc_now().replace("-", "").replace(":", "")
    staged = output_dir / "candidate.tif"
    validation = write_submission(p, template, staged, tags={"strategy": config["name"],
                                  "arm": selected["arm"], "seed": str(config["seed"]),
                                  "floor": str(selected["floor"]), "emission": selected["emission"],
                                  "selection_sha256": selection_sha})
    filename = f"riftline-{selected['arm']}-{timestamp}-{validation['sha256'][:10]}.tif"
    staged.rename(output_dir / filename)
    validation["file"] = filename
    old_path = ROOT / "legacy/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif"
    with rasterio.open(old_path) as src:
        if src.shape != valid.shape or src.transform != profile["transform"] or src.crs != profile["crs"]:
            raise ValueError("Legacy comparison grid does not match")
        old = src.read(1)
    difference = int(np.count_nonzero(p[valid] != old[valid]))
    if difference == 0:
        raise ValueError("Candidate repeats the legacy pixel field; not a new experiment")
    note = (f"Riftline {selected['arm']} | sigma=1,3,7 | u={winning_arm['unlabeled_weight']} | "
            f"{selected['emission']} f={selected['floor']} | s={config['seed']} | {validation['sha256'][:10]}")
    report = {"schema_version": 1, "started_at": started, "completed_at": utc_now(),
              "name": "Riftline", "strategy": config["name"], "status": "format-validated; unsubmitted candidate",
              "competition_score": None, "competition_submission_id": None,
              "config": config, "config_sha256": sha256(config_path), "code_sha256": fingerprint,
              "environment": {"python": platform.python_version(), "numpy": np.__version__,
                              "sklearn": sklearn.__version__, "rasterio": rasterio.__version__,
                              "compute": "CPU, two numerical threads; no GPU"},
              "seconds": round(time.monotonic() - start_time, 3), "inputs": input_report["files"],
              "features": feature_meta, "proxy_sha256": sha256(proxy_path),
              "partition": {"block_px": config["block_px"], "buffer_px": config["buffer_px"],
                            "training_folds": [i for i in range(4) if i not in [config['tuning_fold'], config['audit_fold']]],
                            "tuning_fold": config["tuning_fold"], "audit_fold": config["audit_fold"],
                            "train_pixels": int(train_mask.sum()), "tune_pixels": int(tune_mask.sum()),
                            "audit_pixels": int(audit_mask.sum()),
                            "fold_rule": "((row//512)*3 + (col//512)*5) % 4; see configured block_px",
                            "label_independent": True, "masks_disjoint": not bool(np.any(train_mask & (tune_mask | audit_mask)))},
              "training_samples": sample_summary, "refit_samples": refit_samples,
              "arms": arms, "candidates": candidates, "selected": selected,
              "selection_frozen_sha256": selection_sha, "audit": selected_audit, "audit_blocks": audit_blocks,
              "audit_use": "diagnostic only; winner frozen on tuning data before audit; no guarantees on hidden labels",
              "deployment": deployment,
              "final_model_sha256": sha256(model_path), "final_bounded_link_clipped_pixels": final_clipped,
              "artifact": {"filename": filename, "sha256": validation["sha256"], "bytes": validation["bytes"],
                           "note": note, "validation": validation,
                           "new_pixel_field": {"legacy_sha256": sha256(old_path), "different_valid_pixels": difference,
                           "different_fraction": difference / int(valid.sum()),
                           "mean_absolute_difference": float(np.abs(p[valid] - old[valid]).mean()),
                           "meaning": "Difference from inherited artifact, NOT a verified mapping to extradr19's upload"}},
              "limitations": [
                  "No hidden expert labels or authenticated competition upload; leaderboard gain is unknown.",
                  "Only one fixed spatial train/tune/audit split; not multi-fold proof of superiority.",
                  "Published SGMC catalogue used for tuning is not source-independent of the SGMC audit catalogue.",
                  "Cautious unlabeled weighting is heuristic, not an unbiased positive-unlabeled risk estimator.",
                  "100 m context cannot recover all subpixel scarps; no 1 m DEM was used.",
                  ("Published model trains only on folds 2 and 3; full-data refit was rejected for excessive support."
                   if not refit_eligible else "Full-data refit differs from the audited model; its generalization is unmeasured."),
                  "Deployment fallback was introduced after the initial density failure; the already-read audit is diagnostic, not a new independent replication.",
                  "Some template-valid boundary pixels have missing features and use the model's native missing-value routing."
              ]}
    write_json(output_dir / "experiment.json", report)
    write_json(ROOT / "evidence/experiment.json", report)
    write_json(ROOT / "evidence/validation.json", validation)
    print(f"\nPASS: {output_dir / filename}\nNOTE: {note}\nNo competition score has been measured.", flush=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/riftline.json")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--output", type=Path, default=ROOT / "outputs/riftline-v1")
    args = ap.parse_args()
    run(args.config, args.data, args.output)


if __name__ == "__main__":
    main()
