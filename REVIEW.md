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
