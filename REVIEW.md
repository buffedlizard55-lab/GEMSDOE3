# Three-pass review: session 4 (Pindrop), 2026-09-25

Session 4 replaced the published portfolio with **Pindrop v4**, the placement experiment. Current release state is tracked at the end of this file and in `evidence/review.json`; the local suite stands at **148 Python tests** and the real Chromium suite runs here too (**13/13**, pinned npm-distributed Chromium, no system install), and the candidate still has **no measured competition score**.

## Pass 1 — implement and execute

- Read `README.md`, `NEXT_STEPS.md`, `AGENTS.md`, `REVIEW.md`, `research/RESEARCH.md` and the official metric/format pages before changing anything; re-confirmed the session-3 release state (PR #3 merged, hosted CI green, 119 tests) and the leaderboard snapshot recorded in the README (leader 0.3049, extradr19 0.1563).
- Implemented the pre-registered `configs/pindrop-v4.json`: rotation three of the lattice (origin (128,128), train folds [1,2], tune 3, audit 0), two arms (`union-target` known+SGMC with weight 4.0, `discovery-target` catalogue-gap only), two layers (dense ridge `spacing 1`; suppression-spaced nodes `spacing 4` and `5`), twelve emitted-pixel budgets 0.5%–12%, halo [0,2], tip [0,5], a 1.5× refit support gate and a three-file portfolio.
- Wrote `gems3/schedule.py` (candidate eligibility, confidence ranking, suppression order, budget prefix, separation audit), `gems3/pindrop.py` (sweep → freeze → audit → fraction-consistent refit → export), `gems3/pindrop_publish.py` (independent re-validation, hash pinning, ZIP identity, preview render, previous-manifest archive), `gems3/site_pindrop.py` (upload strip, placement algebra, experiment record, results log) and the wiring in `gems3/site.py`; rotated `gems3/geometry.py` onto a parent-index tip API so both callers share one implementation.
- Added `tests/test_schedule.py` (14 regressions: suppression spacing, `spacing = 1` ≡ the ranked dense prefix, separation measurement, tip-ray ranking, validation errors, budget/prefix algebra, and an equal-emitted-budget sparse-versus-dense test under the real metric) and `scripts/record_submission.py` plus an empty `evidence/leaderboard-results.json`, so a platform score can only be recorded with the platform's own submission id and against a file that is actually published.
- Executed run 1 end to end on CPU (570.2 s): frozen `union-target` / `nodes` / spacing 4 / budget 0.0300 / halo 0 / tip 0, three files passing 13/13 strict gates with 0 pixels on supplied labels. The pre-registered second arm **lost** to the union arm and is reported as measured rather than dropped.

## Pass 2 — adversarial review and fixes

- **Real defect found by reading run 1's records against the code that wrote them.** The dense control's portfolio entry, its raster tag and its paste-able Note all recorded the *selected node* policy (layer nodes, spacing 4) although the file had been built with spacing 1. Pixels were unaffected, but a mislabelled control makes the comparison unreportable. Run 1 was preserved as `evidence/pindrop-v4-run1-report.json` and never published; the fix records the file's own policy, and `gems3/pindrop_publish.check_variant_policies` now refuses any report whose recorded policy contradicts its variant. The regression test reproduces the original defect from the preserved run-1 report.
- **Generic reference caveats replaced by measured ones.** Every earlier published file is an all-fold refit, so every fold scored here is in-sample for it, and the fusion files contain the SGMC traces the gap proxy is built from. Each row now says so, and the site renders it.
- **A second cosmetic defect, found by reading the Notes as a human who has to paste them:** the control's Note read "dense ridge control dense". Fixed in the published run 3 (87 characters).
- **Duplicate DOM id, found by running the real Chromium suite locally instead of waiting on CI.** Publishing the session-3 archive gave the home page two portfolios, and both rendered `id="portfolio-status"`; Playwright's strict locators failed with "resolved to 2 elements". The archived block now owns `portfolio-status-portfolio-previous`, and a Python test asserts that no rendered page repeats an element id. The earlier sessions had recorded that no browser could run in this sandbox; that is no longer true — `npm ci && node scripts/run_browser_tests.cjs` runs the pinned npm-distributed Chromium over `build/site`, and **13/13 passed locally** (`evidence/browser-tests.json`). The README and this review now say so.
- **A CI-only test defect fixed by reproducing CI locally.** `data/sample_submission.tif` is not committed, so a new test that read it failed on the runner while passing here; the suite now falls back to the byte-identical committed mirror. Verified by running the full suite with `data/` moved aside: 148 passed, `scripts/check_published.py` still exits 0.
- **Archived advice was still instructing.** The home page's session-3 block was rendered with the live heading "Upload … first. Paste its Note." although the live block above it is the current recommendation. `portfolio_section` now renders an archived manifest as history ("Kept for comparison", eyebrow marked ARCHIVED, badges prefixed PREVIOUS), and a test asserts the live block instructs and the history block does not.
- **Upload order corrected for the user's actual constraint.** The portfolio had been ordered by experiment number, which put a deliberately weaker control in the second of three weekly upload slots. It is now ordered by value — nodes, discovery, dense control — and the control carries an explicit "CONTROL · UPLOAD LAST" badge and its own rationale on the site.
- **Reproducibility measured with a third full run, not assumed.** Frozen selection identical; the published `nodes` file and the dense control were pixel-identical across all three runs (0 differing pixels inside the template mask); the `discovery-target` file differed in **116 of 155,021** emitted pixels between run 1 and runs 2–3, so that arm's retraining is not bit-reproducible. Cause not established (threaded estimator; its audit known-DTI moved 1e-4). Recorded in `evidence/pindrop-v4-reproducibility.json` and stated in the README instead of claiming blanket determinism.
- **Four test/artifact mismatches reconciled to the artifacts, never by inventing values.** The policy tie-break test asserted the wrong direction (`nodes` sorts before `ridge`, so the node layer wins a tie); the tip-ray test asserted the wrong masking semantics (the supplied-label proxy drops the ray from the emission, leaving the genuine node counted); the metric-algebra test read numeric constants from a config field that holds prose; the experiments-page test searched for a capitalised word that the rendered page does not use. Each was corrected to the measured artefact behaviour, and the budget-saturation caveat (the k=4 schedule saturates below 3%) is now stated on the site and in the README rather than left implicit.

## Pass 3 — original request and release recheck

- Re-read the preserved brief line by line and mapped each requirement to the current state: the upstream snapshot is preserved under `legacy/`; a genuinely different strategy (placement, not mass) was executed on real data; the one-click TIF is the first element of the home page and of the executive summary with `#submit-now` before `#portfolio`; every file has a unique filename and a ≤120-character Note that carries its hash prefix; the `"Predicted values must be in range [0, 1]"` rejection class is addressed by construction, by an independent validator and by a troubleshooting section; official sources are listed with links in the source register; no step required manual input from the user; three explicit passes were run; a pull request was opened and merged.
- Final local verification: **148 Python tests pass**, **13/13 real Chromium checks pass locally**, `ruff check gems3/ tests/` clean, `scripts/check_published.py` exits 0, and `gems3.site` renders all six pages from the published JSON with the live portfolio (3 cards), the archived Coverline block and the Riftline fallback in that order. The deterministic-rebuild test caught one stale render (the verification page was rendered before the session-4 review record was updated) and the pages were rebuilt; the test then passed unchanged.
- Quality improvement made in this pass: the publisher's `pindrop-preview.png` was rendered but never linked, so the experiments page now shows it with a caption that says what the 5x pooling hides (green = the 155,021 emitted single-pixel nodes, amber = the SGMC traces behind the gap proxy; the file is isolated pixels, not a filled map), and a test asserts the figure, the caption and the asset.
- Site-level re-check of the acceptance criteria: the strip names file 1, its pixels, its format gates, its size, its direct `.tif`, its single-file ZIP and its paste-able Note; the executive summary carries the six submission steps; the verification page renders the results log in its explicit empty state until a real platform response is recorded.
- Release state: recorded in `evidence/review.json` and `evidence/github-access.json`. PR #8 is open with the session-4 work; its first hosted Chromium run failed on the duplicate DOM id that pass 2 then fixed locally, and **GitHub authentication failed before the fix could be pushed** (`gh` and `git` both return bad credentials; no credential value was read or stored). The final commit therefore sits on `arena/01a0d8fd-gemsdoe3` locally, the PR is unmerged and the Pages deployment is unverified until GitHub is reconnected in Arena.

## Evidence added this session

- `configs/pindrop-v4.json`, `gems3/schedule.py`, `gems3/pindrop.py`, `gems3/pindrop_publish.py`, `gems3/site_pindrop.py`
- `evidence/pindrop-v4-run3.txt`, `evidence/pindrop-v4-run1-report.json`, `evidence/pindrop-v4-run1-selection-frozen.json`, `evidence/pindrop-v4-errata.json`, `evidence/pindrop-v4-reproducibility.json`
- `docs/data/pindrop-experiment.json`, `docs/data/portfolio.json`, `docs/data/portfolio-coverage-v3.json`, `docs/assets/pindrop-preview.png`
- `tests/test_schedule.py`, `tests/test_pindrop.py` (14 tests), `scripts/record_submission.py`, `evidence/leaderboard-results.json`
- `research/RESEARCH.md` §9 (the derivation, the measured layer comparison and the retained negative result)

## Non-negotiable limits

A local format pass is not platform acceptance. A catalogue diagnostic is not hidden-label accuracy. A prior account score is not an artifact mapping. Repeating one audit is not independent replication. Retrieved quotes do not certify every scientific interpretation or legal condition. No 1 m DEM, third independent catalogue, GPU experiment, completed historical pseudo-label folds 2–3, authenticated competition upload, or higher competition score is claimed. One published file's arm is not bit-reproducible across retrainings, and that is stated rather than hidden.

---

# Session 3 review (Coverline) — preserved

Session 3 replaced the published portfolio with the metric-derived **Coverline v3** set. Current release state is tracked at the end of this file and in `evidence/review.json`; the local suite stands at **119 Python tests**, the Chromium spec was extended but cannot run in this sandbox (hosted CI runs it), and the candidate still has **no measured competition score**.

## Pass 1 — implement and execute

- Read `README.md`, `NEXT_STEPS.md`, `AGENTS.md`, the preserved brief and the official metric/format page before changing anything; re-confirmed the session-2 release state (PR #2 merged, hosted CI green, 110 tests).
- Implemented the pre-registered `configs/coverage-v3.json` in `gems3/coverage.py`: a 12-level support sweep whose floors come from `floor_for_support`, a β/α-weighted classifier arm (`positive_weight` 4.0, the metric's own false-negative/false-positive ratio) beside the regression control, halo [0,2] and tip-ray [0,5] policies, robust-minimum selection over `sgmc-gap` / `all-SGMC` / held-out supplied labels with deterministic tie-breaks, the wide-support rule, a 1.5× refit gate and three exports (`fusion`, `wide`, `ml`).
- Rotated the spatial partition (`block_origin_px` (256,256), 512 px blocks, 48 px buffer; train folds [0,3], tune 1, audit 2) so it does not reuse session 2's tune/audit geography, and made the config refuse the v2 roles. Disclosure is written into the run record and the site.
- Wrote `gems3/coverage_publish.py` (template re-hash, independent strict re-validation, distinct-hash gate, ZIP-namelist identity, previous-manifest archive, max-pool preview PNG, slim report) and `gems3/site_coverage.py` plus wiring in `gems3/site.py`: the upload strip first on the home page, the metric-algebra section, the EXPERIMENT 003 section and a one-paragraph summary for the executive page.
- Executed the experiment end to end on CPU: run 1 completed in 664.4 s (frozen `tversky-weighted-classifier` support 4%, halo 2, tip 5; wide support 12%) and produced three format-validated rasters.
- Added `tests/test_coverage.py` (quantile floors, halo/known masking on a real distance-transform fixture, marginal identity and monotonicity, rotated-partition properties, rank determinism) and kept the three publisher gates.

## Pass 2 — adversarial review and fixes

- **Found a real defect by verifying run 1's output against the keys the publisher and site read.** `marginal_value_tuning` was unscorable on all twelve rows (`dti = None`, `TP_w = FN_w = 0`): the table scored the supplied-label context under the mask `region & ~known`, which erases that context's own truth set (the supplied labels *are* the known pixels). Fixed: `marginal_table` now scores every proxy with the selection sweep's own masks, reports the primary proxy's per-pixel economics, the robust minimum and per-proxy detail, and raises rather than publishing an unscorable row. Regression test added; erratum written to `evidence/coverage-v3-errata.json`; corrected run 2 completed in 429.7 s with the table now monotone (0.0386 → 0.1661 across the twelve tranches).
- **Established what is and is not reproducible, by measurement.** Run 1 vs run 2: all 96 candidate floors, emitted fractions, eligible sets, emitted pixel counts and the refit model hash identical; file bytes different. A third run with the *same* source and config (491.7 s) resolved it: pixel arrays are bit-identical across runs (0 differing pixels, max |difference| 0.0), while the only differing GeoTIFF tag is `selection_sha256`, which hashes a frozen-selection record containing `frozen_at` (wall clock). Holdout audit scores drift by ≤5.7e-05 because HistGradientBoosting fitting is not bit-deterministic under threading. Recorded in `evidence/coverage-v3-reproducibility.json`; the erratum's earlier byte-identity expectation is marked superseded by measurement rather than quietly dropped.
- **UX rule caught by test.** The run's descriptive Note was 125 characters, over our own 120-character brevity rule for a form field. The publisher now derives a compact per-file Note (100 / 94 / 93 characters) and keeps the run's full text as `run_note` for traceability.
- **Test defect fixed, not worked around.** A published-report assertion compared a key that does not exist in the slim JSON, raising `KeyError` instead of testing anything. It is replaced by a closed-loop check: the published raster's own `selection_sha256`, `arm` and `variant` tags must equal the published report and manifest, so a report/file mismatch now fails the suite.
- **Site labelling corrected.** The session-3 wiring had left the Gapfinder block labelled "CURRENT EXPERIMENT" and renamed the Riftline block after Gapfinder. Now: 001 · Riftline, 002 · previous Gapfinder, 003 · Coverline. The rendered home page is verified to place `#submit-now` before `#portfolio`.
- **Stale render caught.** After re-publishing with compact Notes, the rendered strip still carried the old text; the strip test failed and the site was rebuilt. This is the loop working, not a silent pass.
- **Browser spec extended for the user's one-step requirement.** The hosted Chromium suite now asserts that `#submit-now` is visible, that its first step carries file 1's `download` filename and `href`, that it contains file 1's Note, and that it precedes `#portfolio` in the DOM. Playwright still cannot run in this sandbox (no browser); hosted CI is the authority and the spec was syntax-checked with `node --check`.
- **Independently re-checked the published artifacts** with Rasterio: 13/13 gates per file, exactly 0 pixels on any supplied-label pixel, distinct hashes, ZIPs containing exactly their TIF, and the template hash re-verified against the experiment's recorded input.

## Pass 3 — original request and release recheck

- Re-read the preserved brief line by line and mapped it to the current state (recorded in `evidence/review.json`): upstream copy preserved; a genuinely different strategy executed with real data; one-step download obvious at the top of the site and in the executive summary; unique filename and ≤120-character Note per file; the [0,1] rejection class addressed by construction and by an independent validator; official-source register with links; three explicit passes with test evidence.
- Quality improvements made in this pass: the site's algebra text now states the exact improvement test `a·(1 − 0.2·DTI) > 0.2·DTI·b` beside the leading-order break-even column, and the README carries the v3 numbers, the reproducibility result and the corrected caveats.
- Final local verification: **119 Python tests pass**, `ruff check gems3/ tests/` clean, `node --check` clean, all six pages re-rendered from the published JSON.
- Release state: **PR #3 merged into `main`** (merge commit `fb87915`). [Pull-request CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100426189) (Python + real Chromium), [post-merge CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100580048) and the [Pages deployment](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36100579392) all report success; the deployed v3 manifest was read back through the research tool and recorded in `evidence/pages-deployment-v3.json`. Deployment and CI are not a competition score.

## Evidence added this session

- `evidence/coverage-v3-run.txt`, `evidence/coverage-v3-repro.txt`, `evidence/coverage-v3-reproducibility.json`, `evidence/coverage-v3-errata.json`
- `outputs/coverage-v3/experiment.json`, `outputs/coverage-v3/selection-frozen.json`, `outputs/coverage-v3/source/`
- `docs/data/coverage-experiment.json`, `docs/data/portfolio.json`, `docs/data/portfolio-gapfinder-v2.json`
- `tests/test_coverage.py`, `tests/browser/site.spec.cjs`, `evidence/session3-pass*-tests.xml`

# Three-pass review: session 2 (Gapfinder), 2026-09-25

## Pass 1: implement and execute
- Read README/brief, AGENTS, NEXT_STEPS and REVIEW first. Carried next steps: refit distribution shift (fixed with fraction-consistent sampling), 48 px buffer, new tune/audit rotation.
- Read the official staff clarifications through Discourse raw endpoints (11516 mask is pixel-exact and near-known is fully penalised; 11536 continuations count as new; 11527 sources are secret and Phase 2 truth is updated from Phase 1 submissions). Added them, plus the SGMC ScienceBase page (1:1M scale, 2026 successor release), to `research/sources.json` with exact quotes.
- Implemented `gems3/geometry.py`, `gems3/gapfinder.py` and `gems3/gapfinder_publish.py`, plus the site sections in `gems3/site_gapfinder.py`.
- **v1:** selected sgmc-target f=0.35 h=1 L=0. A post-hoc diagnostic showed it finds held-out supplied faults poorly (0.108), so we made a disclosed **v2 amendment** that adds the known proxy to selection.
- **v2 took four attempts** (`evidence/gapfinder-v2-errata.json`):
  1. A leak in the known proxy (tip rays credited against their own source traces) was caught in the log and the run aborted.
  2. The run's source-integrity guard stopped it after we edited a docstring mid-run.
  3. The run completed, but its audit row described a tie-broken policy (h=0) that differed from the deployed one (h=2).
  4. The published run. Frozen winner and all 90 candidates are identical to attempt 3, and the audit now scores the deployed policy.
- **Published:** fusion / ML-only / SGMC-gap GeoTIFFs and ZIPs. Each passed 13/13 gates, is strictly binary, has 0 pixels on supplied labels, and has a unique filename and Note.
- 110 Python tests passed.

## Pass 2: adversarial review and fixes
- **Real bug found by browser tests:** `app.js` rewrote *every* `.filename` and the first `.file-details` on the page with the Riftline identity. After a Riftline browser build, the portfolio cards would have shown the wrong file. Fixed by scoping to `#submission`, and added a regression test.
- Added a real-browser portfolio test. For every file it checks the download filename, SHA-256 of the downloaded bytes, independent raster validation, and that the Note copies exactly. Home and summary both lead with the portfolio.
- `scripts/verify_live.py` now verifies every portfolio TIF/ZIP byte-for-byte after deployment. The local HTTP check passed 10/10 (`evidence/local-http-verification-session2.json`).
- SGMC provenance traced: legacy fetch script, official USGS FeatureServer, fault RuleIDs only, GeoJSON SHA-256 pinned. Public domain.
- Corrected overstatements: the diagnostics docstring ("cap binding" became "lowest floors ineligible"), the README's Riftline sentence, and the limitation on binary emission.
- Kept, not edited: the hand-typed `frozen_before_run` time in `configs/gapfinder-v2.json` is wrong (machine time 04:29:07Z). The file is hash-bound to the run, so the erratum is recorded instead.
- **Results:** 110 Python tests (`evidence/session2-pass2-tests.xml`) and 13 Chromium tests (`evidence/browser-tests.json`) passed.

## Pass 3: original request recheck
- Re-read the full preserved brief. Coverage:
  - unique submission: three new files, tested as distinct from Riftline and the legacy file;
  - one-click download first on home and summary, with copyable Notes;
  - range-error class blocked by strict gates;
  - executive-summary steps updated;
  - source table with official links, extended;
  - feed (existing workflow; new sources pending the first scheduled check);
  - limitations and access (README, NEXT_STEPS, experiments page);
  - three passes; PR and merge.
- Added Gapfinder-specific limitations to the experiments page, including the selection weakness and the fact that the audit is not independent.
- **Not claimed:** any leaderboard score, any improvement over 0.3049, source-independent generalisation, or public deployment before the merged Pages response is verified.

---

# Three-pass review — 2026-09-25

Three local implementation/review passes were executed. The initial GitHub authentication failure is historical: access has been restored, [PR #1](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/1) exists, and [hosted CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36091380405) passed. The PR and deployment workflow are the authoritative current release state; earlier local passes are not themselves deployment proof. The candidate has no measured competition score. Machine-readable status and request coverage are in `evidence/review.json`.

## Pass 1 — implement and execute

- Imported the full upstream snapshot and independently verified **387 Git blob identities**. Preserved source, original site and evidence in `legacy/`. Five large feature-stack parts are externalized from new Git history, not from the local import; pinned restoration is implemented.
- Autonomously reassembled and measured real inputs. The template has **5,167,373 valid pixels**, including 60,988 positives despite the official all-absence example description. Feature coverage omits 3,061 template-valid pixels and includes 1,540 pixels outside that footprint. Geometry/mask, not example values, controls export.
- Executed three CPU model arms. Context-distance won the fixed tuning rule; local audit union DTI was **0.2361075389** versus **0.20891** for the raw control. These are catalogue diagnostics, not comparable to the public 0.3049 / 0.1563 scores.
- The all-data refit emitted **11.2964%** against a predeclared 8% cap and correctly aborted. Retained the unchanged tuning-selected holdout model at **6.8218%** support. The deployment fallback was introduced after that failure; the policy revision is disclosed, not retroactively called pre-registration. No audit-driven arm/threshold/cap change.
- Published a real new TIF/ZIP and compressed browser field/mask. **452,194** template-valid pixels differ from the archived ensemble. No evidence associates that old artifact with extradr19’s actual upload.
- Implemented the active six-page site, executive submission guide, measured prediction preview, source/claim tables, source feed and workflow code. Preserved the original prompt and core values.
- End-of-pass result: **71 Python/unit/artifact checks and 8 Chromium checks passed** after fixing the missing review-file link and a headless single-process test-runner issue.

## Pass 2 — adversarial review and fixes

- Exhaustive min/max/finite/mask/CRS/shape/dtype checks; corrupt or missing files fail closed. Range tests include NaN, infinities, negatives, >1, hidden mask holes and all-zero format-valid controls.
- Compared DTI to brute-force equations and the independent inherited implementation. Verified global-neighborhood semantics for spatial masks and honest null scores for no-truth regions.
- Added binary-truth and cached-ridge input guards. Feature caches now bind the actual implementation hash, not merely a manually incremented version.
- Staging now excludes raw training data, `.git`, environments and secrets, rejects root/source/outside/symlink destinations, and removes only its own fixed generated subtrees.
- Browser generation checks compressed and decoded hashes, independent footprint bits, every pixel, TIFF georeferencing and a complete self-read. Mixed page/manifest versions are rejected. Receipt time is the build time; switching to the direct file resets filename/hash/Note to the canonical identity.
- Feed failures retain previous success times and score evidence. Changed quotes, malformed leaderboards, missing sources, future timestamps and stale records never manufacture a fresh success. HTTPS downgrade redirects are refused.
- Fixed the shell downloader’s interpreter selection. Added a configured GitHub-CLI fallback without TLS bypass or manual token requests. The attempted real missing-local-part restore was blocked by raw-host TLS restrictions followed by the GitHub connection’s **401**; no error response was installed. Mocked success/failure tests cover the fallback; a real successful fallback is **not claimed**.
- Executed label-free inference from the frozen model with regenerated, implementation-bound features. The complete pixel hash **matched the published field exactly**: `41eeffea9cc25d49593ae5f0e359d53502eedccef8b34d935577cb0bde03fb04`.
- Preserved exact executed model code/config separately from later guard fixes. The selected context and cautious-unlabeled arrays repeated bit-for-bit; the raw-feature control did not. Its first array was not retained, so the magnitude/cause of that variation remains unknown.
- Identified the independence limit: 32 px covers the 30 px feature radius, not all feature-plus-ridge-postprocessing support. A larger-buffer/rotated audit is queued; no statistical-independence or significance claim is made.
- End-of-pass result: **93 Python checks and 8 Chromium checks passed**.

## Pass 3 — original request, reproducibility and release recheck

- Re-read the entire README and preserved user request, then audited each requirement. Checked the final file, model lineage, data/source table, unique filename/Note, guide, uncertainty statements, paths, automation and remaining work.
- Added sub-float32-resolution range regressions and rejected masked-array holes that could otherwise lose their mask on conversion.
- Publisher independently recomputes support and actual legacy pixel difference instead of trusting report fields. It verifies the executed code/config bundle before accepting its identity.
- Rechecked official leaderboard through the research tool: DARD **0.3049**, alexoktaba **0.2993**, HardcoreTechGod **0.2854**, extradr19 **0.1563**, rank 18. Read the official metric/format again. The source feed still flags all 15 failed raw-HTTP refresh attempts; the separate primary-tool observation is not disguised as an HTTP success.
- Independently checked the archived comparison TIF: it is format-valid. The source-footprint mismatch and the user's earlier rejection are not falsely assigned to that particular file.
- **99 Python tests passed, no warnings. 11 real Chromium tests passed**, including real download + Rasterio validation, corrupt payload rejection, functional source filters/navigation, stale/unavailable feeds, mobile width, same-origin assets, mixed releases, receipt/direct-file identity and JavaScript-off fallback. Fixed the no-JavaScript test to inspect the rendered fallback element rather than Playwright’s excluded `noscript` container.
- Verified the actual **local HTTP** page and TIF, ZIP, field and mask byte hashes. This is not a public Pages deployment claim. Current screenshots were inspected at desktop and mobile sizes.
- Added bounded post-deployment HTTP byte verification to the Pages workflow, and weekly CPU candidate packaging without automatic model promotion, branch writes or DrivenData upload.
- **Initial release interruption (historical):** authenticated GitHub metadata returned 401; GitHub reconnect was requested in Arena. Actual push/PR/merge and public Pages status must be taken from `evidence/github-access.json` / live GitHub checks, not from these local passes. Pages configuration editing had separately returned 403 earlier.

## Evidence

- `provenance/import.json`, `provenance/model-source.json`
- `docs/data/experiment.json`, `docs/data/validation.json`, `docs/data/submission.json`
- `evidence/initial-selection-frozen.json`, `evidence/refit-failure.json`, `evidence/repeatability.json`
- `evidence/pass1-tests.xml`, `evidence/pass2-tests.xml`, `evidence/pass3-tests.xml`
- `evidence/browser-tests.json`, `evidence/browser-validation.json`, `evidence/inference-validation.json`
- `evidence/local-http-verification.json`, `evidence/legacy-format-check.json`, `evidence/github-access.json`

## Non-negotiable limits

A local format pass is not platform acceptance. A catalogue diagnostic is not hidden-label accuracy. A prior account score is not an artifact mapping. Repeating one audit is not independent replication. Retrieved quotes do not certify every scientific interpretation or legal condition. No 1 m DEM/GPU experiment, completed historical pseudo-label folds 2–3, authenticated competition upload, or higher competition score is claimed.
