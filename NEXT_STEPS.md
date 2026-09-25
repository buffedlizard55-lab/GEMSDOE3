# Next steps — session 5 handoff (written at the end of session 4, 2026-09-25)

Read `README.md` (with the preserved brief at the bottom), `AGENTS.md`, `REVIEW.md` and the release record in `evidence/review.json` before changing anything. Then work this list in order.

## Where the project stands

- **Published, unsubmitted:** Pindrop v4 (`docs/data/portfolio.json`). Three rasters in `docs/downloads/pindrop-v4-*`, each 13/13 local format gates, 0 pixels on any supplied-label pixel, with a unique ≤120-character Note. Recommended upload order is by value: **1** `nodes` (frozen winner), **2** `discovery` (independent arm, the hedge), **3** `ridge` (dense control, published last so the week's slots go to the two files with measured support). The upload strip is the first element of the home page and of the executive summary.
- **Measured this session:** frozen policy `union-target` · `nodes` · spacing 4 · budget 0.0300 · halo 0 · tip 0 on rotation three of the lattice (origin (128,128), train [1,2], tune 3, audit 0). Audit fold: spaced nodes gap **0.2202** / all 0.2405 / known 0.2086 / far 0.1999 versus the **dense ridge control** 0.1278 / 0.1634 / 0.1192 / 0.0997. Paired block bootstrap: gap +0.0924 [+0.0209, +0.1465], all +0.0771 [+0.0152, +0.1328]. The pre-registered second arm `discovery-target` **lost** (0.2117 gap) and is published as the hedge, not as an improvement. Layer sweep: nodes k=4 beat dense k=1 at all twelve budgets (`docs/data/pindrop-experiment.json`).
- **Measured reproducibility:** three full runs, identical frozen selection; the two union-arm files were pixel-identical in all three runs; the `discovery-target` file differed in 116 of 155,021 pixels between run 1 and runs 2–3 (`evidence/pindrop-v4-reproducibility.json`). Bytes never match because `selection_sha256` hashes a timestamped frozen-selection record.
- **Found and fixed in review (the first run was never published):** the control file recorded the selected node policy instead of its own dense policy; reference caveats were generic; the control's Note repeated a word. Documented in `evidence/pindrop-v4-errata.json`. The publisher now refuses any report whose recorded policy contradicts its variant, with a regression test that reproduces the original defect from the preserved run-1 report.
- **Not measured:** anything about the hidden expert labels or the leaderboard. No upload, no competition score, no deployment claim outside GitHub.

## Ordered next actions

1. **Submit and record the platform response.** From an enrolled account upload card 1 (`nodes`), then card 2 (`discovery`) if the week's quota allows, and card 3 only if you want the leaderboard to test the spacing hypothesis directly. For every upload write the returned submission ID, exact filename, file SHA-256, timestamp, platform message and public score into `evidence/leaderboard-results.json` with `python scripts/record_submission.py --file docs/downloads/<file>.tif --submission-id <id> --score <score> --status accepted --message "<platform wording>"`. The script refuses a score without a submission id and refuses a file that is not in the published portfolio, so a score can never be attributed by memory. **This is the only action that can establish whether the placement result transfers to the hidden labels.** If the platform rejects a file, keep the exact wording and compare it with `docs/executive_summary.html#rejection`.
2. **Release verification — keep the habit.** The session-4 pull request and its hosted CI are linked in `evidence/review.json`; the Pages deployment record is `evidence/pages-deployment-v4.json` if the follow-up release-record PR landed. Re-read these links after any future merge: a local pass is not deployment proof.
3. **Explain the one non-deterministic file rather than ignoring it.** Re-run `gems3.pindrop` with `OMP_NUM_THREADS=1` and compare the `discovery-target` field with the published one. If the 116-pixel difference disappears, the cause is threaded histogram building; if it persists, look for an unseeded sampler in the discovery arm. Publish whichever answer is measured.
4. **Move the budget lever to the eligibility lever.** The k=4 schedule saturates below a 3% budget, so the sweep's upper rows are duplicates and the published file already emits essentially every admissible node. The next real question is *which candidates are admissible*: pre-register a distance-to-known-fault ring policy (for example "emit only nodes 0.5–3 km from a supplied trace, plus the top-ranked nodes beyond it"), sweep it against the current rule at the same emitted budget, and freeze before the audit as usual.
5. **Rotate the audit again.** Session 4 used rotation three; the footprint still overlaps earlier sessions. Add a fourth rotation with a different `block_origin_px` and fold roles, or raise `buffer_px` to ≥64, and re-run the unchanged selection rule so the audit becomes a second, less-correlated check.
6. **Run the bounded 3DEP 1 m DEM pilot on a GitHub runner.** USGS hosts are blocked from this sandbox (`legacy/data/dem_links.json` holds 722 resolved tile pairs). Use free official 3DEP tiles only, a small window, and pre-register the comparison (10 m derivative context versus the current 100 m stack). Report negative results.
7. **Break SGMC circularity with a third catalogue.** The two union-family files train partly on SGMC; the discovery arm avoids that but lost on the proxy. Add one independent public fault source (for example the 2026 SGMC GeMS successor DOI `10.5066/P1A3DQZK`, a state geological survey layer, or the GEM Global Active Faults database if it can be fetched through the GitHub bridge) and score the *existing* published files against it, source-held-out, before training on it.
8. **Resolve the legacy pseudo-label folds 2–3** (`legacy/data/evidence/pseudo_labels/`) so pooled historical claims can either be completed or formally withdrawn.
9. **Only then consider new model work:** ridge-snapping the 1:1M SGMC traces to the 100 m grid, a proper non-negative PU risk estimator instead of the heuristic weight, or pseudo-label self-training. Each needs a pre-registered config in `configs/`, a rotated partition and the same freeze-before-audit discipline.

## Verified access limits (unchanged)

- Sandbox egress: GitHub and PyPI work; `drivendata.org`, `docs.nlr.gov`, `sciencebase.gov`, `usgs.gov`/`prd-tnm.s3.amazonaws.com`, `dropbox.com` and `raw.githubusercontent.com` are blocked. Use the Arena research tool for page text and a GitHub runner for USGS downloads.
- The competition data tab needs an authenticated account; the local inputs were restored through the pinned upstream bridge and validated locally (`evidence/data.json`).
- No credentials are stored anywhere in this repository. Never paste passwords or tokens into chat or files.

## Reproduce the current release

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
bash scripts/download_competition_data.sh && python scripts/prepare_data.py
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.pindrop --config configs/pindrop-v4.json --output outputs/pindrop-v4-run3
python -m gems3.pindrop_publish --report outputs/pindrop-v4-run3/experiment.json
python -m gems3.site && python scripts/check_published.py && python -m pytest
python scripts/stage_site.py && python -m http.server 8000 --bind 0.0.0.0 --directory build/site
```

Expect the frozen selection `union-target / nodes / spacing 4 / budget 0.0300 / halo 0 / tip 0`, the same three 155,021-pixel files, and the identical pixels for the two union-arm files (the discovery arm may differ by ~1e-4 of its pixels; see item 3). Roughly 9 minutes of CPU for the experiment on two cores.
