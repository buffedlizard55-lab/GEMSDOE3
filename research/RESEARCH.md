# Research ledger: distinguish a scientific hypothesis from a scored improvement

Reviewed 2026-09-25. This is a bounded primary-source review, not a claim that all literature has been searched. `sources.json` lists the exact claims checked and supports the scheduled feed. Historical wider research is preserved at `legacy/docs/literature.md`; its old verification timestamps are not refreshed by copying it.

## 1. The target matters more than the architecture

The [official problem](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) describes new expert-labeled faults outside the existing public database as the initial test population, followed by expert revision for final awards. Submission predictions must cover **all faults**, not only new ones. Consequently, do not erase known faults from final predictions, and do not treat reproducing the known catalogue as proof of discovering new ones.

**Implemented test:** report known, proxy-only and their union separately on an untouched spatial audit. The union is a local diagnostic, not an approximation with a known error bound to the hidden score. Never average two DTI ratios to manufacture union DTI; recompute TP/FP/FN on the union truth.

## 2. Incomplete labels are not verified negatives

[Hermant et al. (2025), §5.1](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf) retains only tiles containing a mapped positive to reduce imbalance and mapping-observation bias. The paper uses 10 m data and also illustrates differences of up to 400 m between USGS and its local labels in Figure 2. These are findings about that study, not a measurement of every competition label.

**Implemented hypothesis:** compare an unlabeled weight of 0.25 against 1.0 with identical samples and context; regress a 300 m triangular proximity target rather than only exact trace pixels. This is explicitly a heuristic. Sampling changes apparent class prevalence; confidence is not a calibrated probability. Blindly deleting all unlabeled regions or copying SGMC faults into the output would not test genuine discovery.

[Positive-Unlabeled Learning with Non-Negative Risk Estimator (NeurIPS 2017)](https://proceedings.neurips.cc/paper/2017/hash/7cce53cf90577442771720a370c3c723-Abstract.html) motivates a future principled comparison. **Not implemented:** its non-negative risk estimator, class-prior estimation or a proof of missingness assumptions. Do not label the current weighted regressor “nnPU.”

## 3. Spatial context and honest validation

[Roberts et al. (2017), abstract](https://doi.org/10.1111/ecog.02881) describes underestimation of prediction error when dependencies are ignored, recommends blocked cross-validation, and warns that the blocking design can itself change interpolation/extrapolation difficulty.

**Implemented:** label-independent 51.2 km blocks, eroded 3.2 km interiors; distinct training, tuning and audit folds. Features use Gaussian scales 100, 300 and 700 m, with finite context support accounted for in the buffer. Choose a recipe only on tuning fold 0; write its SHA-256 before audit fold 1 is queried. Report each tuning-selected ablation on the same audit. Do not select a second winner after looking at that table.

**Limitations:** one split, a small number of spatial units, incomplete audit labels, shared source geography, and full-data refit. Repeat across rotated folds and a genuinely independent source before claiming robust gain. A random-pixel validation result would not fix these limitations.

## 4. Geometry without catalogue copying

The [official about page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/) discusses remote sensing, elevation and geophysical contrasts as evidence for fault mapping. [GeoDAWN's USGS source](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) documents multiple survey blocks and flight specifications, a reason to inspect spatial transfer and acquisition artifacts rather than assume stationary input quality.

**Implemented:** 19 raw numeric bands; local relief, gradient magnitude, signed curvature and curvature anisotropy for four bands at three scales. Hessian-normal nonmaximum suppression extracts oriented ridges from predicted confidence, rather than thresholding and thinning the inherited ensemble. No coordinate columns, label-distance feature, proxy value, or sample-submission values are model inputs. Label distance is only the supervised **target**.

**Risks:** topographic edges may be roads, drainage or lithologic contacts; geophysical boundaries do not prove a fault. The algorithm does not claim structural-geology verification. Spatial review and high-resolution controls remain necessary.

## 5. The metric does not make a surrogate into hidden truth

The [official metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric) uses max confidence weighted by a triangular distance kernel, radius 300 m, alpha 0.2 and beta 0.8. Our implementation is checked against brute force and the inherited independent implementation. It retains confidence values, does not threshold them inside scoring, and accounts for neighboring truth/predictions outside a scoring subregion when computing distance credit.

**Implemented:** a fixed small emission grid, explicit non-degeneracy limits, and a frozen selection decision. Fewer false negatives are weighted more heavily, but that is not permission to emit the entire footprint or tune incessantly against a public leaderboard. The rules specify three uploads per week, so local experiments must be used efficiently.

## 6. Public data and licensing

| Source | Status / allowed use | Current role |
|---|---|---|
| [Competition data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) | Login/enrollment required; cannot authenticate here | Bytes restored from supplied mirror's hash-pinned bridge, not independently reauthenticated |
| [GeoDAWN](https://doi.org/10.5066/P93LGLVQ) | USGS landing page marks CC0 1.0 | Supplied feature stack |
| [INGENIOUS](https://gdr.openei.org/submissions/1391) | CC BY 4.0 on official landing page; attribution required | Provenance of supplied data; no new external training labels added |
| [SGMC](https://pubs.usgs.gov/publication/ds1052) | Published USGS compilation; metadata identifies scales 1:50,000 to 1:1,000,000 and unreconciled state boundaries | Inherited code-2 proxy for tuning/diagnostic audit only |
| [USGS 3DEP](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services) | Free without use restrictions, per USGS | Next pilot; **not used** in this artifact |
| [Mattéo et al. (2021)](https://doi.org/10.1029/2020JB021269) | Publisher marks article open access / CC BY-NC-ND; this does not authorize every model/data reuse | Organizer-recommended research pointer; not reproduced or redistributed |

The complete inherited DEM URL index and larger source catalogue remain available for audit. Do not relabel all their links “currently verified”: this session did not independently fetch every tile.

## 8. The metric algebra decides the emission budget (session 3)

The [official metric section](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric) was re-read verbatim on 2026-09-25 (both content chunks, quotes in `sources.json` id `metric-equations`/`metric-worked-example`). With alpha = 0.2, beta = 0.8 and the triangular kernel k(d) = max(1 - d/300 m, 0), the distance-weighted Tversky index is

    DTI = TP_w / (TP_w + 0.2*FP_w + 0.8*FN_w)

**Derivation used to design Coverline v3 (binary p = 1 emission).** Adding one emitted pixel x changes the three weighted counts by:

* TP_w: + (k(d_x) - k_old) if x becomes the best cover of a truth pixel at distance d_x, else 0;
* FN_w: the negative of that same quantity, because FN_w is the sum of `1 - best cover` per truth pixel;
* FP_w: + (1 - k(d_x)), the pixel's own false-positive weight, because FP_w sums `p(x)*(1 - max_g k)`.

So `delta denominator = 0.2*(coverage credit gained) + 0.2*(1 - k(d_x))`, and both terms are at most 0.2. Three consequences:

1. **Every emitted pixel costs at most 0.2**, and exactly 0.2 when it lies more than 300 m from any truth pixel.
2. A pixel pays for itself only if the coverage credit it adds exceeds `0.2 * current DTI`. At the public lead of 0.3049 the break-even is 0.061, i.e. roughly within 2.8 px (280 m) of truth that no other emitted pixel covers.
3. Scoring is a *covering* problem: what matters is how much of the hidden truth is covered, not how confident the classifier was. Dense far-field emission and redundant parallel traces are pure cost, while a small extra tranche that reaches uncovered truth is nearly free.

**Implemented (Experiment 003, `gems3/coverage.py`):** a 12-level support sweep with data-driven floors, a beta/alpha-weighted classifier arm (positive weight 4) beside the regression control, a half-block rotated partition with reassigned train/tune/audit roles, and a per-tranche marginal-value table published in `docs/data/coverage-experiment.json`.

**Considered and rejected — do not re-litigate without new evidence.** Emitting the supplied catalogue as a "free hedge" (in case the final round scored the public faults) was rejected. Staff state the mask is pixel-exact and that known pixels "do not count towards penalty terms" (`sources.json` id `mask-excluded`), so the hedge is free but also worthless, and it would confound the fusion-minus-ml measurement that isolates the SGMC contribution. The published files therefore keep zero on every supplied-label pixel.

**Measured outcome (run 2, `evidence/coverage-v3-run.txt`; table in `docs/data/coverage-experiment.json`).** The published tranches are nested, so each row is exactly the pixels the extra support added. Credit per added pixel (added TP_w / added pixels) against the row's leading-order break-even (0.2 * DTI): 0.5% -> 0.0678 vs 0.0077; 1.5% -> 0.1199 vs 0.0186; 3% -> 0.1003 vs 0.0332; 4% -> 0.0917 vs 0.0397; 6% -> 0.0709 vs 0.0468; 8% -> 0.0574 vs 0.0485; 10% -> 0.0420 vs 0.0478; 12% -> 0.0248 vs 0.0449. The first eight tranches pay for themselves; from 10% the added pixels cost more denominator than they buy. That is the measured reason the pre-registered rule stopped at 4% support (robust min DTI 0.1965) while the third published file sits at 12% (0.1760) as an explicit recall probe.

**The exact test, not just the leading-order one.** A tranche with added numerator credit `a` and added false-positive weight `b` raises DTI exactly when `a * (1 - 0.2 * DTI) > 0.2 * DTI * b`, i.e. `D*a > 0.2*TP*(a+b)`. The per-pixel break-even column omits the `(1 - 0.2*DTI)` factor and the `b` term, so the site publishes added FP_w beside it and states both forms. Both readings were checked on all twelve rows of run 2 and agree on every one.

**Defect found in review (session 3, pass 2).** The first run's table was vacuous: `marginal_table` scored the supplied-label context with the mask `region & ~known`, which erases that context's own truth set, so all twelve rows came back `dti = None` and `TP_w = FN_w = 0` (recorded in `evidence/coverage-v3-errata.json`). The function now scores every proxy with the selection sweep's own masks, reports the primary proxy's economics plus the robust minimum, and raises rather than publishing an unscorable row; regression test `tests/test_coverage.py::test_marginal_table_scores_the_supplied_labels_instead_of_erasing_them`.

**Reproducibility measured, not assumed (`evidence/coverage-v3-reproducibility.json`).** Three runs of this recipe (two sources, one) produced **bit-identical pixel arrays** for all three published files (0 differing pixels, max |difference| 0.0, identical emitted counts 246,258 / 195,126 / 624,025) and identical frozen decisions (96/96 support floors, selection, wide policy, refit model hash). The **file bytes still differ between runs**: the only differing GeoTIFF tag is `selection_sha256`, which hashes `selection-frozen.json`, which records a wall-clock `frozen_at`. The holdout-field audit scores also drift by up to 5.7e-05 because HistGradientBoosting fitting is not bit-deterministic under threading. A byte hash therefore cannot serve as a cross-run identity here; the pixel array and the captured decision layer can.

**Limits.** The derivation assumes binary emission at p = 1 and an exactly known kernel; it says nothing about *where* the hidden faults are. A local catalogue gain is still not a leaderboard score, and the rotated partition still overlaps the previous split.

## 9. Placement, not mass: the emission geometry follows from the metric (session 4)

**Claim.** Under the official metric the *set* of emitted pixels, not the confidence value attached to them, is the decision. The metric page states that `TP_w` and `FP_w` are built from *maxima over the 300 m neighbourhood* (`sources.json` id `metric-equations`, quote: "TP𝑤=3.00,FP𝑤=1.89,FN𝑤=2.00"), and the worked example confirms that credit is a maximum, not a sum. For a binary emission at p = 1:

* a truth pixel earns the credit of the single best prediction inside a 3-pixel triangular kernel;
* every prediction pixel costs `0.2 × (1 − k(d))`, so a second prediction four pixels along the same trace adds no numerator credit and still pays its own false-positive weight;
* therefore a set of predictions spaced at half the kernel width covers the same trace as a dense line while paying a fraction of the denominator cost.

**Largest spacing that cannot lose coverage.** A trace point midway between two nodes is at distance `spacing / 2`. Requiring `spacing / 2 < R = 3 px` gives `spacing ≤ 5 px`, i.e. the kernel's Nyquist limit. At `spacing = 4` the worst-case midpoint distance is 2.0 px; at 5 it is 2.5 px. Beyond 6 the midpoint falls outside the kernel and coverage is lost, so the layer is *not* free to sparsify further.

**Implementation.** `gems3/schedule.py`: rank candidates by confidence, accept a pixel only when no accepted node lies inside a suppression square of half-width `spacing − 1`, and take a prefix of that order as the budget. `spacing = 1` suppresses nothing and therefore *is* the dense ridge emission at a confidence floor, which makes the control a one-parameter change rather than a different pipeline. `gems3/pindrop.py` sweeps both layers over the same twelve emitted-pixel budgets.

**Measured on the tuning fold of the session-4 rotation (public SGMC-gap proxy, identical budgets).** Credit per emitted pixel (added TP<sub>w</sub> ÷ emitted pixels): dense ridge 0.0084–0.0112, spaced nodes 0.0179–0.0341 across the sweep. Gap DTI at 1% budget: ridge 0.0553, nodes k=4 0.1703, nodes k=5 0.1765. At 3%: ridge 0.1426, nodes k=4 0.2083. The audit fold gives the same ordering (nodes 0.2202 vs dense control 0.1278), and the paired block bootstrap of that difference excludes zero (gap +0.0924, CI95 [0.0209, 0.1465]).

**What this does not show.** The proxy truth is the public SGMC compilation, not the hidden expert labels; an in-sample or SGMC-derived reference file can score far higher on that same proxy (session 3's fusion file scores 0.6207 because it *contains* the proxy's traces), so cross-session proxy numbers are not comparable. The sparse encoding is a metric-aware *encoding* of a fault trace: it says nothing about whether faults are dotted in reality, and it does not create coverage that the underlying model does not already have.

**Negative result kept.** The `discovery-target` arm — the same estimator trained only on catalogue pixels that the supplied labels do not contain — did **not** beat the union arm on the audit fold (0.2117 vs 0.2202 gap; paired bootstrap +0.0085 [0.0008, 0.0152] in favour of the union arm). Training on the "unmapped population" therefore did not buy generalisation here; it is reported as measured rather than dropped.

## 7. Decision ladder for the next experiments

1. Establish a format-valid, genuinely different candidate with a reproducible CPU run. Record artifact identity and all local results, even negative ones.
2. Upload the next candidate only through the enrolled account, retain its exact filename/hash, Note, public submission ID and score; do not infer that mapping from an account-level best score.
3. Rotate spatial folds using the same pre-registered small candidate set; report paired block effects. Avoid uncontrolled hyperparameter fishing.
4. Build a small 1 m DEM pilot: license + tile hash, verify CRS/vertical datum/nodata, derive at 10 m then aggregate to the exact 100 m grid; never upsample the 100 m stack and call it lidar.
5. Test source-held-out performance before reviving SGMC pseudo-labeling. The historical pooled report says only folds 0 and 1 are present and explicitly flags source circularity; a proxy gain is not independent discovery evidence.
6. Compare a well-specified PU estimator and a small patch model against the CPU control. Run genuine inference and metric parity on CPU first; expensive GPU training is justified by measured pilot evidence, not promises.

**No measured public improvement is asserted in this document.** Read `docs/data/experiment.json` for actual executed results and `docs/data/feed.json` for dated public scores.
