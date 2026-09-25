# Three-pass review — 2026-09-25

Three local implementation/review passes were executed. **GitHub release is blocked by a subsequently failing connection (HTTP 401), not falsely marked deployed.** The candidate has no measured competition score. Machine-readable status and request coverage are in `evidence/review.json`.

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
- **Blocked release steps:** authenticated GitHub metadata returned 401; GitHub reconnect was requested in Arena. Actual push/PR/merge and public Pages status must be taken from `evidence/github-access.json` / live GitHub checks, not from these local passes. Pages configuration editing had separately returned 403 earlier.

## Evidence

- `provenance/import.json`, `provenance/model-source.json`
- `docs/data/experiment.json`, `docs/data/validation.json`, `docs/data/submission.json`
- `evidence/initial-selection-frozen.json`, `evidence/refit-failure.json`, `evidence/repeatability.json`
- `evidence/pass1-tests.xml`, `evidence/pass2-tests.xml`, `evidence/pass3-tests.xml`
- `evidence/browser-tests.json`, `evidence/browser-validation.json`, `evidence/inference-validation.json`
- `evidence/local-http-verification.json`, `evidence/legacy-format-check.json`, `evidence/github-access.json`

## Non-negotiable limits

A local format pass is not platform acceptance. A catalogue diagnostic is not hidden-label accuracy. A prior account score is not an artifact mapping. Repeating one audit is not independent replication. Retrieved quotes do not certify every scientific interpretation or legal condition. No 1 m DEM/GPU experiment, completed historical pseudo-label folds 2–3, authenticated competition upload, or higher competition score is claimed.
