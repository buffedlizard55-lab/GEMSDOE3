# Next steps — session 4 handoff (written at the end of session 3, 2026-09-25)

Read `README.md` (with the preserved brief at the bottom), `AGENTS.md`, `REVIEW.md` and the release record in `evidence/review.json` before changing anything. Then work this list in order.

## Where the project stands

- **Published, unsubmitted:** Coverline v3 (`docs/data/portfolio.json`, order fusion → wide → ml). Three rasters in `docs/downloads/coverage-v3-*`, each 13/13 local format gates, 0 pixels on any supplied-label pixel, with a ≤120-character Note. The upload strip is first on the home page and in the executive summary.
- **Measured this session:** frozen policy `tversky-weighted-classifier` support 4%, halo 2, tip 5 (wide probe at 12%); audit fold 2 gap 0.2009 / all 0.2120 / known 0.1731 versus the regression control 0.1864 / 0.2013 / 0.1728; paired bootstrap interval includes zero. The per-tranche marginal table shows the first eight tranches paying for themselves and the 10–12% tranches not paying (`docs/data/coverage-experiment.json`).
- **Measured reproducibility:** pixel arrays bit-identical across three runs; file bytes differ only through the timestamped `selection_sha256` tag; holdout audit drift ≤5.7e-05 (`evidence/coverage-v3-reproducibility.json`).
- **Not measured:** anything about the hidden expert labels or the leaderboard. No upload, no competition score, no deployment claim outside GitHub.

## Ordered next actions

1. **Submit and record the platform response.** From an enrolled account upload file 1 (then file 2 or 3 as the week's quota allows). For every upload, write the returned submission ID, exact filename, file SHA-256, timestamp, platform message and public score into `evidence/leaderboard-results.json`. Never record a score without its submission ID, and never map an account-level score to a file without one. This is the only action that can establish whether the metric-derived budget beats 0.3049.
2. **Release verification — done in session 3, keep the habit.** [PR #3](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/3) is merged (merge commit `fb87915`); [pull-request CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100426189) (Python + real Chromium, including the new strip-first assertions), [post-merge CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100580048) and the [Pages deployment](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100579392) all succeeded, and the deployed manifest was read back through the research tool (`evidence/pages-deployment-v3.json`). Re-check these links after any future merge; a local pass is not deployment proof.
3. **Rotate the audit again.** Session 3 rotated the lattice by half a block; fold 2 still overlaps geography that session 2 used. Add a third rotation (different `block_origin_px` and fold roles), or raise `buffer_px` to ≥64, and re-run the selection rule unchanged so the audit becomes a second, less-correlated check.
4. **Run the bounded 3DEP 1 m DEM pilot on a GitHub runner.** USGS hosts are blocked from this sandbox (`legacy/data/dem_links.json` holds 722 resolved tile pairs). Use free official 3DEP tiles only, a small window, and pre-register the comparison (context bands at 10 m derivative scale versus the current 100 m stack). Report negative results.
5. **Break SGMC circularity with a third catalogue.** The fusion file's SGMC component cannot be scored locally on SGMC. Add one more independent public fault source (for example the 2026 SGMC GeMS successor DOI `10.5066/P1A3DQZK`, or a state geological survey layer) and score the *existing* published files against it, source-held-out, before training on it.
6. **Resolve the legacy pseudo-label folds 2–3** (`legacy/data/evidence/pseudo_labels/`) so pooled historical claims can either be completed or formally withdrawn.
7. **Only then consider new model work:** ridge-snapping the 1:1M SGMC traces to the 100 m grid, a proper non-negative PU risk estimator instead of the heuristic weight, or pseudo-label self-training. Each needs a pre-registered config, a rotated partition and the same freeze-before-audit discipline in `configs/`.

## Verified access limits (unchanged)

- Sandbox egress: GitHub and PyPI work; `drivendata.org`, `docs.nlr.gov`, `sciencebase.gov`, `usgs.gov`/`prd-tnm.s3.amazonaws.com`, `dropbox.com` and `raw.githubusercontent.com` are blocked. Use the Arena research tool for page text and a GitHub runner for USGS downloads.
- The competition data tab needs an authenticated account; the local inputs were restored through the pinned upstream bridge and validated locally (`evidence/data.json`).
- No credentials are stored anywhere in this repository. Never paste passwords or tokens into chat or files.

## Reproduce the current release

```bash
bash scripts/download_competition_data.sh          # restores the five bridge parts
python scripts/prepare_data.py
OMP_NUM_THREADS=2 python -m gems3.coverage --config configs/coverage-v3.json      # ~7-11 min CPU, ~2.2 GB RSS
python -m gems3.coverage_publish --report outputs/coverage-v3/experiment.json
python -m gems3.site
python -m pytest                                    # 119 tests
node --check tests/browser/site.spec.cjs            # browser suite runs in hosted CI
```

## Traps — do not repeat these

- Do **not** re-run the published v3 experiment to "refresh" it: the published files and the frozen `selection_sha256` tag are the record. A new run changes the timestamped tag and therefore every file hash (pixels stay identical).
- Do **not** treat a file hash as a cross-run artifact identity. Use the pixel array or the captured decision layer.
- Do **not** relax the ≤120-character Note rule or the "no pixel on a supplied label" guarantee.
- Do **not** re-open the catalogue hedge: staff state the supplied-label mask is pixel-exact and that those pixels "do not count towards penalty terms" (`research/sources.json` id `mask-excluded`), so emitting them is free but worthless and would confound fusion-minus-ml.
- Do **not** weaken the publisher's 13 gates, the ZIP identity check, or the closed-loop test that the published raster's tags match the published report.
- Do **not** claim a competition score, a deployment or an upload without the platform response recorded in `evidence/leaderboard-results.json`.
