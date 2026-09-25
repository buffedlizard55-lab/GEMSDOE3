# Riftline · GEMSDOE3

**Start every work session here.** Read this README, the preserved project brief below, `AGENTS.md`, `NEXT_STEPS.md`, and the latest evidence before changing the project.

## The outcome we are building

A one-click, **format-validated GeoTIFF submission** for the DOE GEMS Prize, supported by reproducible experiments, honest evaluation, a clean website and a timestamped official-source feed. Aim to discover previously unmapped faults and compete at the top of the leaderboard—not just reproduce the public training catalogue.

**Maximize P(Win):** prioritize scientific evidence, spatial generalization, rule compliance and useful experiments over optimistic claims. **Own the Outcome:** implement, execute, inspect the actual result, fix failures and leave the next session a reliable base.

- **Planned Pages URL (publication not verified yet):** https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html
- **Planned executive-summary URL:** https://buffedlizard55-lab.github.io/GEMSDOE3/docs/executive_summary.html
- **Official competition:** https://www.drivendata.org/competitions/306/competition-doe-gems/
- **Requirements and metric:** https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- **Official rules:** https://docs.nlr.gov/docs/fy26osti/96647.pdf

The website's download card is the first actionable section. It identifies the artifact, short submission Note, checks, and **unsubmitted / score unknown** status. A local catalogue score is never presented as a leaderboard score. The public leaderboard was independently read on 2026-09-25: leader **0.3049**, extradr19 **0.1563**. We do not know the exact file associated with that account's submission. See `docs/data/feed.json` for timestamps and subsequent changes.

## Current verified result — 2026-09-25

- **Ready locally:** `docs/downloads/riftline-context-distance-20260925T011817Z-7b6010637a.tif` (1,015,914 bytes), plus a ZIP containing exactly that TIF. The live preview has the download/generation buttons.
- **Note:** `Riftline context-distance | sigma=1,3,7 | u=1.0 | binary-ridge f=0.22 | s=20260925 | 7b6010637a`
- **Measured:** 13 format checks; 452,194 pixels different from the archived comparison; label-free frozen-model inference matches every published pixel. **99 Python tests and 11 real Chromium tests passed** after three local review passes.
- **Model limit:** the all-data refit failed the 8% support guard; the unchanged selected spatial-holdout model is published instead. One diagnostic split, no independent replication, no competition upload or measured score gain.
- **GitHub release blocked:** the connection began returning HTTP 401. Reconnect GitHub in Arena—never post credentials. Local readiness does **not** establish a pushed branch, PR, merge, hosted CI run or public deployment. Consult `evidence/github-access.json` for the measured operation status; the URLs above are intended destinations, not proof this version is live.
- **Feed honesty:** all 15 direct HTTP source refreshes were blocked in this sandbox and remain flagged. The public leaderboard was separately re-read through the research tool. Scheduled workflow code is ready but is not active on main until it is published.

## What was copied, and what is new

The starting GEMSDOE3 repository contained only a 10-byte README. The complete **387-file upstream snapshot** at `buffedlizard55-lab/GEMSDOE@cceebbdcf9a7d2890bb0665defcb54dfc66ae452` was downloaded and each file checked against its Git blob ID. Source, original site, historical results, tests and workflows are preserved under `legacy/`; see `provenance/import.json` and `provenance/upstream-tree.json`. Original `.gitignore` is stored as `.gitignore.upstream`. Historical workflows are not active, and old claims are not new verification.

**Storage exception:** the five feature-stack bridge parts (418,912,844 bytes combined) are available through the pinned upstream snapshot, restored by our downloader and excluded from new Git history. The full upstream Git history is not duplicated. Small original rasters/evidence remain preserved. See `THIRD_PARTY.md` for attribution, rights and source limitations.

**New active strategy:** distance-aware regression using 19 supplied geophysical bands plus label-free multiscale context at 1, 3 and 7 pixels. Compare raw-feature, contextual and cautious-unlabeled-weight arms; select oriented-ridge emission only on a tuning region; freeze that decision before a separate spatial audit; attempt the frozen refit under the same quality guard, retaining the unchanged selected model if the refit fails; reject invalid files before publication. Proxy labels are diagnostic/tuning evidence, never training targets or prediction features. This is PU-inspired weighting, **not** a claim of an unbiased PU estimator or calibrated probabilities.

The primary data-placement blocker is resolved by the pinned bridge. No GPU or DrivenData credentials are required for this CPU experiment. The project still cannot guarantee improvement beyond 0.3049: only an actual competition submission can establish its public score, and final private rankings remain unknown.

## Reproduce without manual data placement

Python 3.11 and Node 22 are the tested runtimes. Node is required for the JavaScript-writer checks in the full Python test suite; the optional real-browser runner additionally uses npm on Linux x64. The public browser/direct download needs no local installation. All commands run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
bash scripts/download_competition_data.sh
python scripts/prepare_data.py
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.train
python -m gems3.publish
python -m gems3.site
python scripts/stage_site.py
python -m pytest
python -m http.server 8000 --bind 0.0.0.0 --directory build/site
# Open /docs/index.html
```

The downloader verifies each segment, total size and whole-file SHA-256 before atomic placement. It will not replace valid data with an HTML login page or a corrupted response. It uses the **user-supplied mirror's inherited GitHub bridge**, not an authenticated official download. The official data tab still requires enrollment. When raw-host HTTPS is blocked, the downloader can use the already configured GitHub CLI for the same pinned public object. That fallback needs a functioning GitHub connection; this session’s attempted fresh-network fallback was blocked by HTTP 401, while all canonical files already placed locally remained intact.

Outputs and trained models live in ignored `outputs/`; input rasters and feature caches in ignored `data/`. Allow several GB of working disk and roughly 3–4 GB RAM for the full-grid CPU experiment. Timing and actual package versions are recorded in the experiment report. Large files are not committed. The website ships only the small validated candidate, compressed pixel payload, mask, manifests and evidence.

```bash
# Recheck any downloaded artifact, independently of the browser:
python scripts/validate_submission.py path/to/file.tif --report evidence/my-validation.json
# Official-source feed (unavailable requests are flagged; last success is preserved):
python -m gems3.feed
```

Frozen-model inference without labels is available with `python -m gems3.infer`; only load a model whose hash is pinned by your trusted experiment manifest. The executed model-side source snapshot is preserved in `evidence/training-source/`. Additional guard-only fixes in active code do not retroactively change that run’s recorded source identity.

A weekly CPU workflow is configured to train and package candidates after publication to the default branch without manual data placement; it does **not** automatically promote a rerun or upload to DrivenData. Real browser tests run with `npm ci && node scripts/run_browser_tests.cjs` (Linux x64, pinned npm Chromium, no system install).

The feed uses fixed primary-source URLs, conservative exact-quote checks, HTTP timeouts, source/content hashes where raw bytes are available, explicit stale states and preserved last-success times. Scheduled GitHub Pages automation is configured separately from training; no hosted execution is claimed while GitHub access is blocked. Scheduled jobs may be delayed or disabled by GitHub; a static page is not a continuously running scraper. The UI reports actual evidence age, not a fabricated “live” state.

## Verification and limitations

- One float32 GeoTIFF band; exact template CRS/shape/affine; finite values in [0,1] inside the template mask; NaN outside; matching nodata/mask. Export never silently clips or fills invalid predictions. The regression model's explicit bounded link is applied before evaluation and logged.
- Browser generation verifies compressed and decoded payload hashes, reference-mask membership, values and generated TIFF read-back. A prevalidated direct file is available when browser generation is unsupported.
- A historical failure had NaN inside the scored footprint. Range errors can also mean negative values, values above one, infinity or other invalid content; no single error message alone proves the cause.
- The mirrored example contains fault positives although the official page describes an all-zero example. Its **grid and mask only** are used. The feature mask differs from the submission mask. These irregularities are recorded in `evidence/data.json`.
- No access to hidden expert labels, DrivenData authenticated upload, or the user's private submissions. Enrollment, eligibility/legal attestations, upload and final submission selection cannot honestly be automated in this unauthenticated session. Never send passwords/tokens in chat.
- The selected context field repeated bit-for-bit, but the raw-feature control’s hash changed across two runs; its original array was not retained for a numeric-difference diagnosis. This is flagged, not called universally deterministic training. The 32 px buffer covers feature context, not all feature-plus-postprocessing support; broader-buffer/rotated audits remain future work.
- No GPU or full 1 m DEM coverage used. Public catalogues are incomplete and biased; one spatial split is not proof of generalization. Existing historical pseudo-label experiments have unresolved source-circularity and missing-fold limits; see `NEXT_STEPS.md`.
- Direct sandbox requests to several official hosts are restricted. Initial primary sources were read through the research tool; scheduled unrestricted GitHub runners can attempt subsequent checks. Network failures remain visible.
- Rules limit submissions to **three per week**, require one final selection, and require disclosure of generative-AI assistance. The website deadline and generic PDF appendix deadline wording are not identical; both are linked and flagged for review. We do not invent a legal resolution.
- Three review passes and actual test/measurement evidence are recorded in `evidence/review.json` and `REVIEW.md`. Verify deployment and PR status from GitHub; never infer them from a successful local build.

## Project map

| Path | Purpose |
|---|---|
| `gems3/` | Active downloader, model, features, metric, strict exporter, feed and publisher |
| `configs/riftline.json` | Fixed experiment/selection rule plus explicitly dated post-failure deployment policy |
| `docs/` | Static, subpath-safe site and download/generation assets |
| `evidence/` | Fresh local measurements and review trail |
| `research/` | Primary-source catalogue, bounded literature review and claim ledger |
| `provenance/` | Exact upstream import manifest and source review provenance |
| `tests/` | Active regression and browser-generation tests |
| `.github/workflows/` | Prepared CI, weekly CPU experiments and source-feed/Pages jobs; hosted activation pending |
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
