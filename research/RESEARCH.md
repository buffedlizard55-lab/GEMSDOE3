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

## 7. Decision ladder for the next experiments

1. Establish a format-valid, genuinely different candidate with a reproducible CPU run. Record artifact identity and all local results, even negative ones.
2. Upload the next candidate only through the enrolled account, retain its exact filename/hash, Note, public submission ID and score; do not infer that mapping from an account-level best score.
3. Rotate spatial folds using the same pre-registered small candidate set; report paired block effects. Avoid uncontrolled hyperparameter fishing.
4. Build a small 1 m DEM pilot: license + tile hash, verify CRS/vertical datum/nodata, derive at 10 m then aggregate to the exact 100 m grid; never upsample the 100 m stack and call it lidar.
5. Test source-held-out performance before reviving SGMC pseudo-labeling. The historical pooled report says only folds 0 and 1 are present and explicitly flags source circularity; a proxy gain is not independent discovery evidence.
6. Compare a well-specified PU estimator and a small patch model against the CPU control. Run genuine inference and metric parity on CPU first; expensive GPU training is justified by measured pilot evidence, not promises.

**No measured public improvement is asserted in this document.** Read `docs/data/experiment.json` for actual executed results and `docs/data/feed.json` for dated public scores.
