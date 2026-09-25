# Start here after reading README.md

## Release handoff

GitHub access is working again. [PR #1](https://github.com/buffedlizard55-lab/GEMSDOE3/pull/1) contains the release on `arena/01a0d603-gemsdoe3`; [its initial hosted CI](https://github.com/buffedlizard55-lab/GEMSDOE3/actions/runs/36091380405) passed the Python/artifact and Chromium verification gates. Consult the PR for the current merge state and Actions for actual Pages deployment and public-byte verification. The earlier 401 failure is preserved as historical evidence, not a current instruction to reconnect.

For future changes, remain on the assigned branch, run the active checks, and use a PR rather than writing to main directly. A CI pass is not a competition score; an Actions configuration is not a deployment. The source-feed workflow includes public page/TIF/ZIP/payload byte-hash verification after deployment. Retain that result before asserting that a new version is live.

## Objective

Produce a reproducible GEMS submission that genuinely improves discovery, with a clear path to leaderboard testing. A format-valid artifact or a local proxy gain is **not** proof of a score above 0.3049.

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

## Ordered next actions

1. **Get a real competition measurement tied to the artifact.** Use the executive summary, keep the exact downloaded TIFF/build hash and Note, upload through the enrolled account, retain submission ID and public score. Only then can we claim an improvement or regression. Do not infer identity from extradr19’s account-level best score. Limit: no DrivenData authentication in this session; no password or token should be posted in chat.
2. **Fix all-data refit distribution shift as a new, versioned experiment.** Current sampling retains all exact positives while capping other strata, so the class/target mixture changes when the training region expands. Test consistent stratified sampling or principled inverse-inclusion weights. Freeze the new recipe before using a fresh/rotated audit; do not simply relax the 8% cap or tune a threshold against the already-read audit.
3. **Rotate spatial folds, then test source transfer.** Increase/ablate the buffer (e.g. 48 px): the present 32 px exceeds the feature-only radius of 30 px but not the full feature-plus-ridge-postprocessing support. Do not call these fields statistically independent merely because target masks are disjoint. Keep the small candidate space and measure paired effects over independent blocks. Existing SGMC source informs tuning; using other SGMC geography is not source independence. Add a genuinely distinct published catalogue only after provenance, overlap and rights checks.
4. **Carry out the prior-session 1 m DEM pilot.** Use a small official USGS tile set, record byte hashes, datum/CRS/mask and licenses, derive at 10 m, aggregate to the exact submission grid, compare to the 100 m control. No 1 m terrain was used in the current artifact. Complete region-wide downloads only if the pilot justifies their resource cost.
5. **Evaluate principled PU loss / patch context on CPU before scaling.** The current unlabeled-weight arm is heuristic, not nnPU. A calibrated class prior or small patch model is a testable upgrade, not an automatic win. Larger deep training benefits from GPU access but is not a blocker to usable CPU submissions.
6. **Resume historical pseudo-label folds only with the right controls.** Complete folds 2 and 3 if still useful, but separate same-source gains from discovery. Do not overwrite or retroactively relabel the preserved upstream evidence. Avoid spending compute merely to strengthen a circular proxy score.
7. **Monitor feed and workflow reliability.** Check actual Pages response, scheduled workflow logs and freshness states. Publisher blocking, changed clauses, disabled Actions schedules, GitHub token restrictions and failed downloads must remain visible. Avoid automatic branch writes; deploy a checked snapshot as a Pages artifact.
8. **Keep run directories versioned.** Do not overwrite raw confidence arrays when comparing reproducibility; the first raw-control array was lost on rerun, so its hash mismatch cannot be quantified retrospectively. Keep failed candidates separate from the published source/model record.
9. **Competition compliance before finalization.** Read latest official rules, eligibility criteria, one-final-submission rule, 3/week quota, date wording, source licenses and generative-AI disclosure. Package code, environment and resource requirements. Clarify discrepancies with organizers; do not invent legal certainty.

## Access/resource limits

- No hidden expert labels or private submission metadata.
- No authenticated DrivenData upload or legal enrollment on behalf of the user.
- No GPU and no claim of large deep-model training this session; full-grid CPU route runs locally.
- Direct requests to some official sources/browser CDNs are restricted in this sandbox. Primary sources were read with the research tool; automated refreshes are attempted on GitHub runners and preserve prior evidence if blocked. A pinned npm Chromium distribution enables real local browser tests without a system install.
- GitHub Pages configuration changes are outside this integration's scope; normal branch pushes/PR and workflow capabilities must be measured separately. Do not call a 403 configuration limitation an authentication failure when git operations work.
