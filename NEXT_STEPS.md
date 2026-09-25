# Start here after reading README.md

## Release handoff

GitHub access is working again. [PR #1](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/1) contains the release on `arena/01a0d603-gemsdoe3`; [its initial hosted CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36091380405) passed the Python/artifact and Chromium verification gates. Consult the PR for the current merge state and Actions for actual Pages deployment and public-byte verification. The earlier 401 failure is preserved as historical evidence, not a current instruction to reconnect.

For future changes, remain on the assigned branch, run the active checks, and use a PR rather than writing to main directly. A CI pass is not a competition score; an Actions configuration is not a deployment. The source-feed workflow includes public page/TIF/ZIP/payload byte-hash verification after deployment. Retain that result before asserting that a new version is live.

## Objective

Produce a reproducible GEMS submission that genuinely improves discovery of faults **absent from the supplied labels**, with a clear path to leaderboard testing. A format-valid artifact or a local proxy gain is **not** proof of a score above 0.3049.

## Carried work reviewed first

- Original repository was absent in this checkout; imported all 387 upstream files and verified Git blob identities. Large bridge parts are externalized, not lost; the active downloader restores canonical inputs.
- Data-placement blocker: resolved autonomously from the hash-pinned bridge and independently measured in `evidence/data.json`.
- Range-error/footprint bug: new fail-closed exporter and exhaustive regression checks, not just an old sanitizer rerun.
- One-click browser generation and a prominent executive summary: active site leads with the actual artifact and Note, not a long report.
- Historical pseudo-label follow-up: the inherited pooled report has folds 0 and 1, while requesting folds 0–3, and flags source circularity. It is preserved as incomplete evidence; no missing-fold scores were invented.
- Original-site deployment race: this repository is already configured for legacy Pages from main:/; the integration cannot edit that setting (403). The new source-feed deployment runs on schedule/manual dispatch, not on push, to avoid racing the automatic merge deployment. Verify the actual deployed response after merging.

## Results/limitations to carry forward

The initial full-data refit exceeded the predeclared 8% support cap (11.2964%). It was not shipped. The unchanged tuning-selected context-distance model uses 6.8218% support and passed that same cap. The fallback was introduced after this deployment failure, not pre-registered before the first run; no model arm, threshold, support cap, or audit-label selection was changed. The repeated audit is not an independent new experiment. See `evidence/refit-failure.json`, `evidence/initial-selection-frozen.json`, and `docs/data/experiment.json`.

The current deployed-model role is explicit in the experiment report. If it is the frozen holdout model, it trained only on spatial folds 2 and 3; do not describe it as an all-data-trained model. Cautious unlabeled weighting did not win this comparison. Preserve that negative result.

## Session 2 summary (Gapfinder)

- The previous next steps were reviewed first. Step 2 (refit distribution shift) is **done**: fraction-consistent sampling, and the Gapfinder refits passed the 8% cap (v1 3.84%, v2 3.46%). Step 3 is partially done: buffer raised to 48 px, a new tune/audit rotation (tune fold 2, audit fold 3), and a second catalogue used as the target.
- Official clarifications (forum 11516, 11536, 11527) changed the objective. Supplied-label pixels are masked, near-label false positives are fully penalised, and continuations count as new. See `research/sources.json` ids `forum-*`.
- Published the Gapfinder v2 portfolio (fusion / ML-only / SGMC-gap). The whole v1 → v2 record, including four v2 attempts, is in `evidence/gapfinder-*` and `evidence/gapfinder-v2-errata.json`.

## Ordered next actions

1. **Upload the portfolio in order and record the scores.** File 1 (fusion), then file 2 (ML-only), then optionally file 3 (SGMC-gap), with the Notes from the site. Record platform submission ID + public score against the SHA prefix in each Note (e.g. `evidence/leaderboard-results.json`).
   - fusion − ml measures the value of adding SGMC traces directly.
   - sgmc-gap alone measures how closely the hidden labels follow the published map.
   - These results decide the next design. Requires the user's enrolled account; never post credentials.
2. **Use the leaderboard result to choose the next pre-registration.**
   - If SGMC-gap alone scores well, hidden labels resemble bedrock-map faults: try the **2026 SGMC GeMS release** (https://doi.org/10.5066/P1A3DQZK), newer and not yet used, and snap its ~1:1M traces onto ridges of the model field.
   - If ML-only ≥ fusion, drop direct SGMC traces and tune model support.
   - Pre-register a support-cap sweep. The proxy prefers support above 8% for some arms, but this is **not** evidence that the leaderboard does.
3. **Fix the selection-rule weakness.** The known proxy ignores halo and tip, so for some arms those were chosen by the mass tie-break. Score the known proxy on the *emitted* field with an explicit rule about known-pixel handling, or select halo/tip on gap/all only.
4. **Use a truly fresh audit.** Fold 3 has now been seen twice. Rotate to a new block origin or offset grid and pre-register before looking. Report paired block-bootstrap effects.
5. **High-resolution terrain pilot** (carried over): run a small, hash-pinned USGS 3DEP 1 m/10 m tile set in GitHub Actions (the sandbox blocks some hosts). Derive scarp/lineament features at 10 m, aggregate to the 100 m grid, and compare against the 100 m control on held-out geography.
6. **A third independent fault source for auditing**, e.g. state survey 1:250k/1:100k maps with licences compatible with the rules. Needed before any source-transfer claim.
7. **Carry-overs:** PU loss / patch models on CPU first; historical pseudo-label folds 2–3 only with source controls; feed/workflow monitoring. The four new `forum-*`/`sgmc-sciencebase` sources show as "not checked" until the scheduled feed runs. Compliance review before final selection (one final file, 3/week, generative-AI disclosure, reproducible code).

## Access/resource limits

- No hidden expert labels or private submission metadata.
- No authenticated DrivenData upload or legal enrollment on behalf of the user.
- No GPU and no claim of large deep-model training this session; full-grid CPU route runs locally.
- Direct requests to some official sources/browser CDNs are restricted in this sandbox. Primary sources were read with the research tool; automated refreshes are attempted on GitHub runners and preserve prior evidence if blocked. A pinned npm Chromium distribution enables real local browser tests without a system install.
- GitHub Pages configuration changes are outside this integration's scope; normal branch pushes/PR and workflow capabilities must be measured separately. Do not call a 403 configuration limitation an authentication failure when git operations work.
