"""Post-hoc diagnostics for Gapfinder v1 (NOT used for selection; run after the recipe was frozen).

1. Cross-source check: how well does each arm's frozen-policy emission find held-out SUPPLIED
   (Qfault/INGENIOUS) faults in the audit fold? An arm that only learned SGMC style would do badly.
2. Support curve: faithful-proxy DTI of the selected arm vs. confidence floor on the TUNING fold,
   to inform the next pre-registration (the 8% cap made the lowest floors ineligible for some arms).
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems3.common import ROOT, read_json, utc_now, write_json  # noqa: E402
from gems3.emission import ridge_mask  # noqa: E402
from gems3.features import spatial_partition  # noqa: E402
from gems3.gapfinder import emit, load_catalogues  # noqa: E402
from gems3.metric import MetricContext  # noqa: E402
from gems3.raster import template_info  # noqa: E402

run = ROOT / "outputs/gapfinder-v1"
rep = read_json(run / "experiment.json")
cfg = rep["config"]
valid, profile = template_info(ROOT / "data/sample_submission.tif")
cat = load_catalogues(valid, profile, ROOT / "data")
known = cat["known"]
folds, interior = spatial_partition(valid.shape, cfg["block_px"], cfg["buffer_px"])
audit = valid & interior & (folds == cfg["audit_fold"])
tune = valid & interior & (folds == cfg["tuning_fold"])
dk = distance_transform_edt(~known).astype("float32")
kctx = MetricContext(known)
out = {"generated_at": utc_now(), "post_hoc": True, "used_for_selection": False, "cross_source": {}, "support_curve": []}
for a in rep["arms"]:
    raw = np.load(run / f"{a['arm']['id']}-holdout.npy")
    b = a["best"]
    ridges = ridge_mask(raw, valid)
    # For the cross-source check the known pixels must be emit-able, so rebuild without the known mask.
    keep = valid & ridges & (raw >= b["floor"])
    s = kctx.score(keep.astype("float32"), audit)
    out["cross_source"][a["arm"]["id"]] = {"policy_floor": b["floor"], "audit_known_dti": s["dti"],
                                          "TP_w": s["TP_w"], "FP_w": s["FP_w"], "truth_pixels": s["truth_pixels"]}
    print(a["arm"]["id"], "audit DTI vs held-out supplied faults: %.4f" % s["dti"])
    if a["arm"]["id"] == rep["selected"]["arm"]:
        gap, allc = MetricContext(cat["sgmc_gap"]), MetricContext(cat["sgmc_all"])
        for f in [0.25, 0.28, 0.3, 0.32, 0.35, 0.38, 0.4, 0.45]:
            p = emit(raw, ridges, valid, known, dk, {}, f, rep["selected"]["halo"], 0)
            m = tune & ~known
            g, al = gap.score(p, m)["dti"], allc.score(p, m)["dti"]
            out["support_curve"].append({"floor": f, "support": float(p[tune].mean()), "gap": g, "all": al})
            print(f"  tune floor {f:.2f} support {p[tune].mean():.3%} gap {g:.4f} all {al:.4f}")
    del raw, ridges
for label, path in (("riftline-published", next((ROOT / "docs/downloads").glob("riftline-*.tif"))),
                    ("legacy-ens12", ROOT / "legacy/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif")):
    q = rasterio.open(path).read(1)
    q = np.where(np.isfinite(q) & valid, q, 0).astype("float32")
    s = kctx.score(q, audit)
    out["cross_source"][label] = {"audit_known_dti": s["dti"], "note": "Riftline trained on folds 2-3 (audit fold 3 in-sample)" if "rift" in label else "training region unknown"}
    print(label, "audit DTI vs supplied faults: %.4f" % s["dti"])
write_json(ROOT / "evidence/gapfinder-diagnostics.json", out)
