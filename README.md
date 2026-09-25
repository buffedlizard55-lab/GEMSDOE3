# Pindrop · GEMSDOE3 (sessions 1–3: Riftline, Gapfinder, Coverline)

**Start every work session here.** Read this README, the preserved project brief below, `AGENTS.md`, `NEXT_STEPS.md`, and the latest evidence before changing the project.

## The outcome we are building

A one-click, **format-validated GeoTIFF submission** for the DOE GEMS Prize, supported by reproducible experiments, honest evaluation, a clean website and a timestamped official-source feed. Aim to discover previously unmapped faults and compete at the top of the leaderboard—not just reproduce the public training catalogue.

**Maximize P(Win):** prioritize scientific evidence, spatial generalization, rule compliance and useful experiments over optimistic claims. **Own the Outcome:** implement, execute, inspect the actual result, fix failures and leave the next session a reliable base.

- **Pages URL (deployment status is tracked below):** https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html
- **Executive-summary URL:** https://buffedlizard55-lab.github.io/GEMSDOE3/docs/executive_summary.html
- **Official competition:** https://www.drivendata.org/competitions/306/competition-doe-gems/
- **Requirements and metric:** https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- **Official rules:** https://docs.nlr.gov/docs/fy26osti/96647.pdf

The website opens with the **Pindrop portfolio**: three format-validated GeoTIFFs in a recommended upload order, above a one-line strip that links file 1, its ZIP and its paste-able Note. Each file has a unique filename, a copyable Note of 120 characters or fewer and an **unsubmitted / score unknown** status. The session-3 Coverline files, the session-2 Gapfinder files and the session-1 Riftline file stay downloadable below as previous candidates, and each archived block is labelled as history rather than advice. A local catalogue score is never presented as a leaderboard score. The public leaderboard was read on 2026-09-25 through the research tool: leader **0.3049** (DARD), alexoktaba 0.2993, HardcoreTechGod 0.2854, extradr19 **0.1563** (rank 21 of 25+ at that read, one submission). The leaderboard rows recorded in `docs/data/feed.json` were re-read on 2026-09-25 through the research tool and are labelled there as a research-tool observation, not an HTTP fetch. We do not know which file was behind that account's submission. See `docs/data/feed.json` for timestamps.

**If you only do one thing:** open the site, click the first card's **Download .tif**, then paste the Note beside it into the DrivenData form. `docs/executive_summary.html#steps` has the six steps, the rule citations and what to do if an upload is rejected.

## Current verified result: Pindrop v4 (session 4, 2026-09-25)

**Upload in this order** (3 uploads/week; one final selection). Card order is value, not experiment number:

| # | File (`docs/downloads/`) | Note to paste | Pixels = 1 |
|---|---|---|---|
| 1 SUBMIT FIRST | `pindrop-v4-nodes-20260925T152420Z-f347b70daa.tif` | `Pindrop v4 nodes \| union-target HGB \| sparse nodes k=4 s=3.000% h=0 L=0 \| f347b70daa` | 155,021 (3.000%) |
| 2 SUBMIT SECOND | `pindrop-v4-discovery-20260925T152423Z-37f9d5b855.tif` | `Pindrop v4 discovery \| discovery-target HGB \| catalogue-gap k=4 s=3.000% h=0 L=0 \| 37f9d5b855` | 155,021 (3.000%) |
| 3 CONTROL · UPLOAD LAST | `pindrop-v4-ridge-20260925T152422Z-4e03fc9705.tif` | `Pindrop v4 ridge \| union-target HGB \| dense ridge control s=3.000% h=0 L=0 \| 4e03fc9705` | 155,021 (3.000%) |

Each file passed 13/13 strict format gates on read-back: exact template CRS, transform and shape; float32; NaN exactly outside the template mask; finite values in [0, 1] inside; **0 pixels on a supplied label**. Each ZIP contains exactly its TIF and re-hashes to the same digest. Card 3 is a deliberate control, not a weaker guess: the same arm, budget, halo and tip as card 1 with the suppression switched off, so the leaderboard can test the placement hypothesis directly. It is published last precisely because three slots per week should be spent on the two files with a measured reason to be believed.

**Why this strategy is different.** Sessions 1–3 asked *which pixel* to emit. Session 4 asks *where in the metric's own kernel*. The official metric credits a truth pixel from the **single best** prediction inside a 300 m triangular kernel, so two predictions four pixels apart along one trace add nearly no credit while both paying the false-positive weight — a dense line pays several times for the same coverage. `gems3/schedule.py` ranks every candidate pixel by model confidence and accepts one only when no accepted node lies inside a suppression square of half-width `spacing − 1`, then takes a prefix of that order as the budget. `spacing = 1` suppresses nothing and therefore *is* the dense confidence-floor emission, which is why the control is a one-parameter change rather than a different pipeline. The largest spacing that cannot lose coverage at the midpoint of a trace is `2R − 1 = 5 px`; the sweep compared 1, 4 and 5 on measured proxy DTI and the pre-registered rule chose 4. Derivation and measurements: `research/RESEARCH.md` §9.

**Measured locally** (proxy DTI on public catalogues; **not** leaderboard-comparable, and the hidden labels stay hidden):

- Frozen selection (`outputs/pindrop-v4-run3/selection-frozen.json`, hashed into every file's `selection_sha256` tag before the audit fold was scored): `union-target` · `nodes` · spacing 4 · budget 0.0300 · halo 0 · tip 0.
- Rotation three of the same lattice: `block_origin_px` (128, 128), train folds [1, 2], tune 3, audit 0 — roles never used by sessions 1–3. Partition 1,754,513 / 911,224 / 776,210 pixels, 5,701 fault tips, 48,465 far-from-catalogue truth pixels.
- Audit fold, holdout-trained models, identical emitted-pixel budgets: **spaced nodes gap 0.2202 / all 0.2405 / known 0.2086 / far 0.1999** versus the **dense ridge control 0.1278 / 0.1634 / 0.1192 / 0.0997**. Paired block bootstrap of the difference: gap **+0.0924** CI95 [+0.0209, +0.1465], all **+0.0771** [+0.0152, +0.1328]; both intervals exclude zero.
- The pre-registered second question — does an arm trained only on catalogue pixels the supplied labels omit generalise better? — was **answered no**: `discovery-target` scored gap 0.2117 against the union arm's 0.2202 (paired bootstrap +0.0085 [+0.0008, +0.0152] for the union arm). It is published as card 2 as the honest hedge, not as an improvement.
- Layer sweep on the tuning fold: nodes k=4 beat dense ridge k=1 at **all twelve budgets** (at 3%: 0.2083 vs 0.1426). Credit per emitted pixel: dense 0.0084–0.0114, nodes 0.0179–0.0406 — the sparse schedule gets 2–4× more credit for the same pixel bill.
- All-fold refit accepted (1.5× support gate, support 3.00%, 0 pixels clipped); the published pixels come from `union-target-refit.joblib` (`d79a8c55152a76c7…`).
- Full record: `evidence/pindrop-v4-run3.txt`, `outputs/pindrop-v4-run3/experiment.json`, `docs/data/pindrop-experiment.json`, `docs/data/portfolio.json` and the site's Experiments page.

**Honest caveats for v4:**

- **Unscored.** No upload has been made. Only DrivenData can say whether any of these files beats 0.1563 or 0.3049.
- **The budget barely binds at the selected spacing.** The k=4 schedule in the tuning region saturates at 27,304 nodes; every budget from 3% upward emits the same field, and the published file carries 155,021 of the 155,467 available nodes. The selection rule therefore chose "the whole spaced schedule", and the sweep's higher rows are duplicates, not larger emissions — the site labels those rows by measured emitted fraction for that reason.
- **The proxy cannot rank the two arms fairly.** The union arm trains partly on SGMC-gap pixels, which *are* the gap proxy's truth, so its proxy advantage over the discovery arm is partly circular. The controlled comparison is nodes versus dense control (same arm, budget and folds), and that is the only one this session treats as evidence.
- **Every earlier published file is in-sample here.** The three files compared in the audit's reference table were all-fold refits from sessions 1–3, and the fusion files contain the SGMC traces the gap proxy is built from; their audit numbers are upper bounds, and each row now carries that caveat explicitly.
- **Reproducibility measured, not assumed.** Three full runs produced the identical frozen selection; the published node file and the dense control were **pixel-identical in all three runs** (0 differing pixels). The discovery file differed in 116 of its 155,021 emitted pixels between run 1 and runs 2–3, so that arm's retraining is **not** bit-reproducible; the cause is not established (the estimator is threaded, and its audit known-DTI also moved 1e-4). Bytes are never identical: `selection_sha256` hashes a frozen-selection record containing its freeze timestamp. See `evidence/pindrop-v4-reproducibility.json`.
- **Three defects were found in review and fixed, and the first run was never published.** A mislabelled control policy and its Note, generic reference caveats, and a duplicated word in the control's Note are documented in `evidence/pindrop-v4-errata.json`; the publisher now refuses any report whose recorded policy contradicts its variant, with a regression test that reproduces the original defect from the preserved run-1 report.
- **Rotation, not independence.** Folds are a third rotation of one lattice over one footprint; overlapping geography is disclosed, not hidden.
- Limits: no independent third catalogue, no 1 m DEM, no GPU, no hidden labels, no authenticated upload.

### Previous candidate: Coverline v3 (session 3)

**Archived, not advice.** These were session 3's recommendations and are kept verbatim below for audit; the current recommendation is the Pindrop portfolio above. The three files remain downloadable and are still valid candidates for the one final selection, and the site's "previous portfolio" block is labelled the same way.

**Upload order from that session** (3 uploads/week; one final selection):

| # | File (`docs/downloads/`) | Note to paste | Pixels = 1 |
|---|---|---|---|
| 1 SUBMIT FIRST | `coverage-v3-fusion-20260925T054015Z-3ccf68834a.tif` | `Coverline v3 fusion \| Tversky-weighted classifier \| s=4.00% h=2 L=5 \| + SGMC-gap traces \| 3ccf68834a` | 246,258 (4.77%) |
| 2 SUBMIT SECOND | `coverage-v3-wide-20260925T054019Z-0ac095a7ed.tif` | `Coverline v3 wide \| Tversky-weighted classifier \| s=12.00% h=0 L=5 \| recall probe \| 0ac095a7ed` | 624,025 (12.08%) |
| 3 OPTIONAL THIRD | `coverage-v3-ml-20260925T054017Z-92d5062aea.tif` | `Coverline v3 ml \| Tversky-weighted classifier \| s=4.00% h=2 L=5 \| no SGMC traces \| 92d5062aea` | 195,126 (3.78%) |

Each file passed 13/13 strict format gates on read-back: exact template CRS, transform and shape; float32; NaN exactly outside the mask; finite values in [0,1] inside; **0 pixels on a supplied label**. Each ZIP contains exactly its TIF and re-hashes to the same digest. This is what fixes the earlier "Predicted values must be in range [0, 1]" rejection class.

**Why this strategy is different.** Session 3 reads the official metric as an *emission budget*, not a classifier problem. With α = 0.2 and β = 0.8, adding one emitted pixel raises the Tversky denominator by `0.2 × (credit it newly contributes) + 0.2 × (1 − k(d))`, which is at most 0.2 — so a pixel must land within ~2.8 px of uncovered truth to pay for itself (`research/RESEARCH.md` §8). Coverline therefore sweeps twelve support levels whose *thresholds* are set so the emission covers a target fraction of the valid grid (0.5%–12%), trains a β/α-weighted classifier (positive weight 4) beside the regression control, and publishes the measured marginal value of every tranche. The first eight tranches pay for themselves (credit per added pixel above the row's break-even); from 10% they do not, which is why the conservative policy is file 1 and the 12% file is labelled a probe.

- Spatial discipline: a **half-block rotated** partition — `block_origin_px` (256, 256), 512 px blocks, 48 px buffer, 4.8 km guard — with train folds [0, 3], tune 1, audit 2. It never reuses Gapfinder v2's tune/audit roles, and the rotation disclosure is in the config and on the site.
- Selection: maximize the minimum of three public proxies (SGMC-gap, all-SGMC, held-out supplied labels) on the tuning fold, tie-break by lower emitted fraction, frozen in `outputs/coverage-v3/selection-frozen.json` **before** the audit fold was scored (`audit_consulted: false`).
- The wide file is the largest-support eligible candidate of the winning arm with robust DTI ≥ 0.75 × the selected value; fusion adds independently mapped USGS SGMC faults the labels omit.

**Measured locally** (proxy DTI on public catalogues; **not** leaderboard-comparable, and the hidden labels stay hidden):
- Frozen policy: `tversky-weighted-classifier`, support 4.00%, floor 0.49407, halo 2 px, tip ray 5 px; emitted fraction 3.43% of the tuning region.
- Audit fold 2, holdout-trained model: gap 0.2009 / all 0.2120 / known 0.1731. The regression control scored gap 0.1864 / all 0.2013 / known 0.1728 on the same fold.
- Paired block bootstrap (20 blocks, 2,000 draws) vs the control: gap +0.0145 [−0.0015, +0.0402], p(A better) 0.9515; all +0.0107 [−0.0030, +0.0334], p 0.9095. **The interval includes zero**: this is a small, not statistically resolved, difference on public stand-ins.
- All-fold refit accepted (3.78% support, 1.5× gate); the published pixels come from the refit model.
- Full record: `evidence/coverage-v3-run.txt`, `outputs/coverage-v3/experiment.json`, `docs/data/coverage-experiment.json`, and the site's Experiments page.

**Honest caveats for v3:**
- **Unscored.** No upload has been made; only DrivenData can say whether any file beats 0.3049.
- **Reproducibility measured, not assumed.** Three runs produced identical pixel arrays (0 differing pixels) and identical frozen decisions, but **not** identical files: the only differing GeoTIFF tag is `selection_sha256`, which covers a timestamped frozen-selection record, and holdout audit scores drift by ≤5.7e-05 under threaded training. See `evidence/coverage-v3-reproducibility.json`.
- **A defect was found in review and fixed.** The first v3 run's marginal table was vacuous (all twelve rows unscorable) because of a mask error; it is documented in `evidence/coverage-v3-errata.json`, fixed, regression-tested and republished, and the decision layer was shown identical between the affected and published runs.
- **Rotation, not independence.** Fold 2 here overlaps geography that v2 used for tuning and audit; the audit is a disclosed rotation, not a fresh survey area.
- **Source circularity.** The fusion file uses SGMC (~1:1,000,000 compilation) as data; scoring it locally on SGMC would be circular, so SGMC traces inside the fusion file are not locally scored.
- Limits: no 1 m DEM, no GPU, no hidden labels, no authenticated upload; one partition.
- **Release:** [PR #3](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/3) merged into `main` (merge commit `fb87915`) after [hosted CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100426189) passed, including the extended Chromium suite. [Post-merge CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100580048) and the [Pages deployment](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100579392) succeeded, and the deployed manifest was read back through the research tool (`evidence/pages-deployment-v3.json`). Deployment is not a score.

### Previous candidate: Gapfinder v2 (session 2)

**Upload in this order** (still downloadable; a valid alternative if you prefer the session-2 evidence):

| # | File (`docs/downloads/`) | Note to paste | Pixels = 1 |
|---|---|---|---|
| 1 SUBMIT FIRST | `gapfinder-v2-fusion-20260925T045011Z-682a7bbbfe.tif` | `Gapfinder v2 fusion \| two-catalogue HGB ridge f=0.4 h=2 L=0 + SGMC-gap traces \| 682a7bbbfe` | 229,468 (4.44%) |
| 2 SUBMIT SECOND | `gapfinder-v2-ml-20260925T045012Z-73e97f79f6.tif` | `Gapfinder v2 ML-only \| two-catalogue HGB ridge f=0.4 h=2 L=0 \| no SGMC traces \| 73e97f79f6` | 178,548 (3.46%) |
| 3 OPTIONAL THIRD | `gapfinder-v2-sgmc-gap-20260925T045014Z-7251c22bb4.tif` | `Gapfinder v2 SGMC-gap only \| USGS SGMC faults >300m from labels \| no model \| 7251c22bb4` | 61,664 (1.19%) |

Each file passed 13/13 strict format gates on read-back: exact template CRS, transform and shape; float32; NaN exactly outside the mask; finite values in [0,1] inside. Each ZIP contains exactly its TIF. No file emits on a supplied-label pixel. This is what fixes the earlier "Predicted values must be in range [0, 1]" rejection class.

**Why this strategy.** DrivenData staff confirmed that supplied USGS/INGENIOUS pixels are masked **pixel-exactly** from scoring, that predictions near known traces but away from new truth are **fully penalised**, and that "new" includes continuations of known systems ([forum 11516](https://community.drivendata.org/raw/11516), [11536](https://community.drivendata.org/raw/11536)). Riftline was trained to reproduce the supplied labels. On-label pixels earn nothing, and near-label pixels are penalised unless new truth is nearby. Gapfinder instead:
- trains on a second, independent public catalogue: USGS SGMC faults, in training regions only;
- never emits on supplied labels, with an optional halo around them;
- optionally extends known fault tips;
- selects on held-out regions with three proxies: SGMC faults >300 m from labels ("gap"), all SGMC faults ("all"), and held-out supplied faults ("known").

The **fusion** file adds the SGMC-gap traces directly. The **ML-only** file omits them, so the score difference between files 1 and 2 measures their value. The **SGMC-gap** file tests the published map on its own.

**Measured locally** (proxy DTI; different truth from the hidden labels, **not** leaderboard-comparable):
- Frozen selection: `two-catalogue-target f=0.40 h=2 L=0`, by max min(gap, all, known) on tuning fold 2.
- Audit fold 3, selected policy: gap 0.182 / all 0.176 / known 0.150.
- Riftline file: gap 0.092 / all 0.156 / known 0.328. Riftline trained on fold 3, so its known score is in-sample.
- Paired block bootstrap vs the supplied-labels-only arm: gap +0.096 [0.053, 0.129], all +0.063 [0.019, 0.096] (7 blocks).
- All-fold refit accepted at 3.46% support (8% cap).
- Full record: `evidence/gapfinder-v2-experiment.json` and the site's Experiments page.

**Honest caveats:**
- **v1 → v2.** v1 (`evidence/gapfinder-v1-*`) picked an SGMC-only model. A post-hoc check showed it finds held-out supplied faults poorly (0.108), so v2 added the known proxy to selection. Fold 3 had already been inspected, so **the v2 audit is not independent**.
- **Four attempts.** v2 took four attempts, all logged in `evidence/gapfinder-v2-errata.json`: a proxy leak we caught, a source-integrity guard stop, an audit/tie-break mismatch, and the published run with an identical frozen selection.
- **Circularity.** SGMC is a ~1:1,000,000 compilation. Trained-on-SGMC/scored-on-SGMC measures geographic transfer, not source transfer.
- **Unscored.** No upload has been made, and only the leaderboard can say whether any file beats 0.3049.

**Tests (session 2 record):** 110 Python tests passed locally, including 11 new Gapfinder tests (portfolio uniqueness, prominence, notes, ZIP content, geometry, sampling, proxy and bootstrap). The current count is 119 (see above); the Chromium suite runs in hosted CI and its status is recorded in `REVIEW.md`.

### Previous candidate: Riftline (session 1)

- `docs/downloads/riftline-context-distance-20260925T011817Z-7b6010637a.tif` (1,015,914 bytes) plus a single-file ZIP. Note: `Riftline context-distance | sigma=1,3,7 | u=1.0 | binary-ridge f=0.22 | s=20260925 | 7b6010637a`. Unscored.
- 13 format checks; 452,194 pixels differ from the archived comparison; label-free frozen-model inference matches every published pixel.
- Model limit: the all-data refit failed the 8% support guard, so the unchanged spatial-holdout model is published.
- Release history: [PR #1](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/1) merged into `main` with [hosted CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36091380405) green. `evidence/github-access.json` preserves the earlier authentication failure and recovery.
- Feed honesty: the initial 15 direct HTTP source refreshes were blocked in the sandbox and remain dated evidence, not fresh successes.

## What was copied, and what is new

The starting GEMSDOE3 repository contained only a 10-byte README. The complete **387-file upstream snapshot** at `buffedlizard55-lab/GEMSDOE@cceebbdcf9a7d2890bb0665defcb54dfc66ae452` was downloaded and each file checked against its Git blob ID. Source, original site, historical results, tests and workflows are preserved under `legacy/`; see `provenance/import.json` and `provenance/upstream-tree.json`. Original `.gitignore` is stored as `.gitignore.upstream`. Historical workflows are not active, and old claims are not new verification.

**Storage exception:** the five feature-stack bridge parts (418,912,844 bytes combined) are available through the pinned upstream snapshot, restored by our downloader and excluded from new Git history. The full upstream Git history is not duplicated. Small original rasters/evidence remain preserved. See `THIRD_PARTY.md` for attribution, rights and source limitations.

**Session 2 strategy (Gapfinder, previous):** train on a second public catalogue (USGS SGMC) inside training regions only, never emit on a supplied label, optionally extend known fault tips, and select on three disjoint-region proxies including held-out supplied faults. It is kept above under "Previous candidate".

**Session 4 strategy (Pindrop, current):** keep session 3's pixel budget and change *where in the metric's kernel* the pixels go. The official metric credits a truth pixel from the single best prediction inside a 300 m kernel, so a dense trace pays several times for one coverage. `gems3/schedule.py` ranks candidates by model confidence and accepts a pixel only when no accepted node lies inside a suppression square of half-width `spacing − 1`, sweeping spacing 1 (the dense control, identical to a confidence floor), 4 and 5 (the Nyquist limit `2R − 1`) against twelve emitted-pixel budgets, then freezing the selection before the audit fold is scored. Measured on a third rotation of the lattice, the spaced schedule scores gap DTI 0.2202 against the dense control's 0.1278 at the identical budget, and the pre-registered second arm (trained only on catalogue pixels the supplied labels omit) lost to the union arm and is published as the hedge rather than as an improvement.

**Session 3 strategy (Coverline, previous):** treat the official metric as an emission budget. Add an oriented-ridge emission whose threshold is set so each tranche covers a target fraction of the valid grid (0.5%-12%), train a beta/alpha-weighted classifier (positive weight 4, the metric's own false-negative/false-positive ratio) beside the regression control, keep the rotation of the spatial partition disclosed, and publish the measured marginal value of every tranche. Server-side selection maximizes the minimum of the same three proxies and freezes before the audit.

**Session 1 strategy (Riftline, now the previous candidate):** distance-aware regression using 19 supplied geophysical bands plus label-free multiscale context at 1, 3 and 7 pixels. Compare raw-feature, contextual and cautious-unlabeled-weight arms; select oriented-ridge emission only on a tuning region; freeze that decision before a separate spatial audit; attempt the frozen refit under the same quality guard, retaining the unchanged selected model if the refit fails; reject invalid files before publication. In Riftline, proxy labels were diagnostic/tuning evidence, never training targets or prediction features. Gapfinder deliberately trains on SGMC; see above. This is PU-inspired weighting, **not** a claim of an unbiased PU estimator or calibrated probabilities.

The primary data-placement blocker is resolved by the pinned bridge. No GPU or DrivenData credentials are required for this CPU experiment. The project still cannot guarantee improvement beyond 0.3049: only an actual competition submission can establish its public score, and final private rankings remain unknown.

## Reproduce without manual data placement

Python 3.11 and Node 22 are the tested runtimes. Node is required for the JavaScript-writer checks in the full Python test suite; the optional real-browser runner additionally uses npm on Linux x64. The public browser/direct download needs no local installation. All commands run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
bash scripts/download_competition_data.sh
python scripts/prepare_data.py
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.train      # session 1: Riftline
python -m gems3.publish
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.gapfinder --config configs/gapfinder-v2.json  # ~7 min CPU
python -m gems3.gapfinder_publish --report outputs/gapfinder-v2/experiment.json
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.coverage --config configs/coverage-v3.json  # session 3: Coverline, ~7-11 min CPU
python -m gems3.coverage_publish --report outputs/coverage-v3/experiment.json
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.pindrop --config configs/pindrop-v4.json --output outputs/pindrop-v4-run3  # session 4: Pindrop, ~9 min CPU
python -m gems3.pindrop_publish --report outputs/pindrop-v4-run3/experiment.json
python -m gems3.site
python scripts/stage_site.py
python -m pytest
python -m http.server 8000 --bind 0.0.0.0 --directory build/site
# Open /docs/index.html
```

The downloader verifies each segment, total size and whole-file SHA-256 before atomic placement. It will not replace valid data with an HTML login page or a corrupted response. It uses the **user-supplied mirror's inherited GitHub bridge**, not an authenticated official download. The official data tab still requires enrollment. When raw-host HTTPS is blocked, the downloader can use the already configured GitHub CLI for the same pinned public object. That fallback needs a functioning GitHub connection; the initial build session’s attempted fresh-network fallback was blocked by HTTP 401, while all canonical files already placed locally remained intact.

Outputs and trained models live in ignored `outputs/`; input rasters and feature caches in ignored `data/`. Allow several GB of working disk and roughly 3–4 GB RAM for the full-grid CPU experiment. Timing and actual package versions are recorded in the experiment report. Large files are not committed. The website ships only the small validated candidate, compressed pixel payload, mask, manifests and evidence.

```bash
# Recheck any downloaded artifact, independently of the browser:
python scripts/validate_submission.py path/to/file.tif --report evidence/my-validation.json
# Official-source feed (unavailable requests are flagged; last success is preserved):
python -m gems3.feed
```

Frozen-model inference without labels is available with `python -m gems3.infer`; only load a model whose hash is pinned by your trusted experiment manifest. The executed model-side source snapshot is preserved in `evidence/training-source/`. Additional guard-only fixes in active code do not retroactively change that run’s recorded source identity.

A weekly CPU workflow is configured to train and package candidates after publication to the default branch without manual data placement; it does **not** automatically promote a rerun or upload to DrivenData. Real browser tests run with `npm ci && node scripts/run_browser_tests.cjs` (Linux x64, pinned npm Chromium, no system install).

The feed uses fixed primary-source URLs, conservative exact-quote checks, HTTP timeouts, source/content hashes where raw bytes are available, explicit stale states and preserved last-success times. Scheduled GitHub Pages automation is configured separately from training; hosted execution and deployment are verified through the linked workflow runs, not inferred from configuration. Scheduled jobs may be delayed or disabled by GitHub; a static page is not a continuously running scraper. The UI reports actual evidence age, not a fabricated “live” state.

## Verification and limitations

- One float32 GeoTIFF band; exact template CRS/shape/affine; finite values in [0,1] inside the template mask; NaN outside; matching nodata/mask. Export never silently clips or fills invalid predictions. The regression model's explicit bounded link is applied before evaluation and logged.
- Browser generation verifies compressed and decoded payload hashes, reference-mask membership, values and generated TIFF read-back. A prevalidated direct file is available when browser generation is unsupported.
- A historical failure had NaN inside the scored footprint. Range errors can also mean negative values, values above one, infinity or other invalid content; no single error message alone proves the cause.
- The mirrored example contains fault positives although the official page describes an all-zero example. Its **grid and mask only** are used. The feature mask differs from the submission mask. These irregularities are recorded in `evidence/data.json`.
- No access to hidden expert labels, DrivenData authenticated upload, or the user's private submissions. Enrollment, eligibility/legal attestations, upload and final submission selection cannot honestly be automated in this unauthenticated session. Never send passwords/tokens in chat.
- **Session 4 control integrity:** the publisher refuses any report whose recorded policy contradicts the file variant it describes (a reviewed run shipped the selected node policy on the dense control) and prints the report path and hash it is publishing; the regression test reproduces the original defect from the preserved run-1 report.
- **Session 4 reproducibility:** the frozen selection and the two union-arm files were pixel-identical across three full runs; the `discovery-target` file differed in 116 of its 155,021 emitted pixels between run 1 and runs 2–3, so that arm's retraining is not bit-reproducible and no claim of determinism is made for it. Cause not established.
- **Session 4 budget caveat:** the k=4 schedule saturates below a 3% budget in the tuning region, so the top rows of the sweep are duplicates of the largest feasible schedule and the published file emits 99.7% of all available nodes.
- The selected context field repeated bit-for-bit, but the raw-feature control’s hash changed across two runs; its original array was not retained for a numeric-difference diagnosis. This is flagged, not called universally deterministic training. The 32 px buffer covers feature context, not all feature-plus-postprocessing support; broader-buffer/rotated audits remain future work.
- No GPU or full 1 m DEM coverage used. Public catalogues are incomplete and biased; one spatial split is not proof of generalization. Existing historical pseudo-label experiments have unresolved source-circularity and missing-fold limits; see `NEXT_STEPS.md`.
- Direct sandbox requests to several official hosts are restricted. Initial primary sources were read through the research tool; scheduled unrestricted GitHub runners can attempt subsequent checks. Network failures remain visible.
- Rules limit submissions to **three per week**, require one final selection, and require disclosure of generative-AI assistance. The website deadline and generic PDF appendix deadline wording are not identical; both are linked and flagged for review. We do not invent a legal resolution.
- **Session 3 reproducibility measured:** three runs of the published recipe gave bit-identical pixel arrays for all three files (0 differing pixels) and identical frozen decisions (96/96 support floors, selection, wide policy, refit model hash), but **different file bytes**, because the `selection_sha256` GeoTIFF tag covers a frozen-selection record that stores a wall-clock timestamp; holdout audit scores drift by up to 5.7e-05. Byte hashes are therefore not a cross-run identity here; `evidence/coverage-v3-reproducibility.json` records the comparison.
- **Session 3 defect, flagged and fixed:** the first v3 run's per-tranche marginal table was unscorable (all twelve rows `dti = None`) because the supplied-label context was scored under a mask that erased its own truth. Fixed, regression-tested (`tests/test_coverage.py`), re-run, and recorded in `evidence/coverage-v3-errata.json`. The frozen decisions were identical before and after the fix.
- Three review passes and actual test/measurement evidence are recorded in `evidence/review.json`, `evidence/session3-pass*-tests.xml` and `REVIEW.md`. Verify deployment and PR status from GitHub; never infer them from a successful local build.

## Project map

| Path | Purpose |
|---|---|
| `gems3/` | Active downloader, model, features, metric, strict exporter, feed and publisher |
| `gems3/gapfinder.py`, `gems3/geometry.py`, `gems3/gapfinder_publish.py`, `gems3/site_gapfinder.py` | Gapfinder experiment, tip geometry, portfolio publisher and site sections |
| `gems3/coverage.py`, `gems3/coverage_publish.py`, `gems3/site_coverage.py` | Coverline v3 experiment (support sweep, metric algebra, rotated partition), its portfolio publisher and its site sections |
| `configs/gapfinder.json`, `configs/gapfinder-v2.json` | Frozen Gapfinder v1 design and the disclosed v2 amendment |
| `configs/coverage-v3.json` | Pre-registered Coverline v3 design (hash-bound into the frozen selection) |
| `configs/riftline.json` | Fixed experiment/selection rule plus explicitly dated post-failure deployment policy |
| `docs/` | Static, subpath-safe site and download/generation assets |
| `evidence/` | Fresh local measurements and review trail |
| `research/` | Primary-source catalogue, bounded literature review and claim ledger |
| `provenance/` | Exact upstream import manifest and source review provenance |
| `tests/` | Active regression and browser-generation tests |
| `.github/workflows/` | CI, weekly CPU experiments and source-feed/Pages jobs; actual run state is recorded in GitHub Actions |
| `legacy/` | Preserved upstream code, site and historical evidence, not active automation |

---

## Original project brief — preserved as the starting point

The following is the user's original request, retained including repeated emphases and historical blocker statements. **Historical claims in this brief are goals/context, not current verification.** Updated measured status is above and in the evidence files.

> Review the repo.
>
> WE NEED TO CREATE A COPY OF this entire repo and site
>
> https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html
>
> But we need to generate a different submission that is unique since the last submission scored extradr19
>
> 7min ago
>
> ⸱
>
> 1 submission
>
> 0.1563
>
> 0.3049 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website. It should be unique, take unique approaches to generating a submission that can score higher than .3049.
>
> Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It should solve the problem of having to manually check everything ourselves and having an up to date current feed.
>
> Review the repo.
>
> The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.
>
> Our Core Values
>
> Maximize P(Win)
>
> “Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.
>
> Own the Outcome
>
> We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.
>
> Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.
>
> Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.
>
> We need to focus on being able to generate a submission into the competition.
>
> The site should be able to generate a TIF file that is required for submission. It should be as easy as download to click a File to submit into the competition. This needs to be in the executive summary or the very beginning of the site. it should be obvious when you visit the site.
>
> I tried to submit the document that i downloaded from the site but it returned this error on the submission form:
>
> "Predicted values must be in range [0, 1]"
>
> Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25
>
> Here is the submission page when i click submit file
>
> New submission
>
> File to submitNo file chosen
>
> You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.
>
> Note (optional)
>
> A short comment to help you or your team tell submissions apart later e.g. clustering with k=25
>
> Create a executive summary subpage that explains exactly how to make a submission into the contest.
>
> Work on the next steps from the previous sessions first.
>
> The goal of this project is to place top of the leaderboard in this competition. The following is the competition:
>
> https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
>
> We need to create a project that can compete and place top of the leaderboard. We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.
>
> This is the guidelines we need to follow. https://www.drivendata.org/competitions/306/competition-doe-gems/
>
> Get familiar with the problem through the overview and problem description, https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/. You might also want to reference additional resources available on the about page, https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/.
>
> Download the data from the data, https://www.drivendata.org/competitions/306/competition-doe-gems/data/, tab.
>
> Create and train your own model. This reference solution, https://github.com/drivendataorg/gems-prize-reference-solution implements a simple approach.
>
> Use your model to generate predictions that match the submission format.
>
> Tell me what are you limitations and what you need access to during this project. We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.
>
> this pdf outlines how submissions must be entered into the competition.
>
> https://docs.nlr.gov/docs/fy26osti/96647.pdf
>
> You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information. this must be done autonomously and must be constantly reviewed and improved upon. Provide suggestions and improvements and implement them.
>
> ❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from https://www.drivendata.org/competitions/306/competition-doe-gems/data/ (verified redirect to login)
>
> See below for links from the above site. See attached files for links from the above site.
>
> https://gdr.openei.org/submissions/1391
>
> Download competition data from https://www.drivendata.org/competitions/306/competition-doe-gems/data/ (requires login) to data/
>
> See links below for competition data:
>
> https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0
>
> https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0
>
> https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0
>
> https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0
>
> https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0
>
> Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.
>
> Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.
>
> Site creation
>
> Create a github page for this repo that has clean ui, user friendly, simple and easy to use. It should be organized and clean.
>
> It should include all relevant information in an easy to read format with official verified links as sources for review. Work line by line verify everything no hallucinations.
>
> **The single remaining blocker to training is data placement**: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).
>
> you need to complete the above task by yourself. Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.
>
> Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.
>
> Run this task through multiple passes.
>
> Pass 1: Implement the task completely and verify the result.
>
> Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.
>
> Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.
>
> Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request. Work line by line verify everything no hallucinations.
>
> Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project. It should be worked on in this next session or the next session. Work line by line verify everything no hallucinations.
