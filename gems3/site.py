"""Render the active static site from measured evidence; no fabricated metrics or live states."""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from .common import ROOT, read_json
from .site_coverage import algebra_section, coverage_experiment_section, coverage_summary, upload_strip
from .site_gapfinder import (
    clarifications_section,
    experiment_section,
    gapfinder_summary,
    load_optional,
    portfolio_section,
    portfolio_verification,
)

COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"
PROBLEM = COMP + "page/967/"
RULES = "https://docs.nlr.gov/docs/fy26osti/96647.pdf"
REPO = "https://github.com/buffedlizard55-lab/GEMSDOE3"


def esc(value):
    return html.escape(str(value), quote=True)


def score(value):
    return "Not measured" if value is None else f"{value:.4f}"


def icon(name):
    paths = {
        "home": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "guide": '<path d="M7 3h8l4 4v14H5V3h2Z M14 3v5h5 M9 12h6 M9 16h6"/>',
        "experiment": '<path d="M9 3h6 M10 3v7L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3 M7 16h10"/>',
        "data": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5 M4 12c0 4 16 4 16 0"/>',
        "research": '<path d="M4 4h6a3 3 0 0 1 3 3v14a5 5 0 0 0-4-2H4V4Z M13 7a3 3 0 0 1 3-3h5v15h-4a5 5 0 0 0-4 2"/>',
        "verify": '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z m-4 9 3 3 5-6"/>',
        "arrow": '<path d="M5 12h14 m-6-6 6 6-6 6"/>',
        "download": '<path d="M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5"/>',
        "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
        "external": '<path d="M9 4H4v16h16v-5 M13 3h8v8 M11 13 10-10"/>',
    }
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths.get(name, paths["arrow"])}</svg>'


NAV = [("index.html", "home", "Mission control"), ("executive_summary.html", "guide", "Executive summary"),
       ("experiments.html", "experiment", "Experiments"), ("sources.html", "data", "Data & sources"),
       ("research.html", "research", "Research log"), ("verification.html", "verify", "Verification")]


def shell(filename, title, body):
    links = []
    for path, glyph, label in NAV:
        active = "active" if path == filename else ""
        current = ' aria-current="page"' if path == filename else ""
        links.append(f'<a href="{path}" class="nav-link {active}"{current}>{icon(glyph)}<span>{label}</span></a>')
    nav = "".join(links)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Riftline: an evidence-first GEMS fault-discovery experiment. Build a locally validated GeoTIFF, inspect the research, and monitor official sources.">
<meta name="theme-color" content="#123a34"><title>{esc(title)} · Riftline / GEMS3</title>
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/site.css">
<script src="assets/geotiff-writer.js" defer></script><script src="assets/submission-builder.js" defer></script><script src="assets/app.js" defer></script></head>
<body><a href="#main" class="skip-link">Skip to content</a>
<aside class="sidebar"><a href="index.html" class="brand" aria-label="Riftline home"><svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="m5 31 9-21 6 12 7-17 8 24 M9 33l9-15 7 15" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/></svg><span>riftline<span class="brand-sub">GEMS DISCOVERY LAB</span></span></a>
<div class="workspace-label">WORKSPACE <span>03</span></div><nav aria-label="Main navigation">{nav}</nav>
<div class="sidebar-bottom"><div class="sidebar-note"><span class="dot"></span> Evidence before confidence<p>A new strategy. A traceable result.<br>No unverified score claims.</p></div>
<a class="side-external" href="{COMP}" target="_blank" rel="noopener noreferrer">Competition {icon('external')}</a><a class="side-external" href="{REPO}" target="_blank" rel="noopener noreferrer">View repository {icon('external')}</a>
<div class="sidebar-version">GEMSDOE3 <span>RESEARCH BUILD</span></div></div></aside>
<div class="main-shell"><header class="topbar"><div class="breadcrumb">DOE GEMS PRIZE <span>/</span> {esc(title)}</div><a href="sources.html#feed" class="feed-status" id="feed-status"><span class="dot neutral"></span> Checking snapshot age</a></header>
<main id="main">{body}</main><footer><span>Riftline / GEMSDOE3 <span class="footer-separator">·</span> Maximize P(Win). Own the Outcome.</span><span><a href="../README.md">Project brief</a><a href="../legacy/docs/index.html">Original site archive ↗</a></span></footer></div>
<noscript><div class="noscript">JavaScript is off. Use the prevalidated TIF download and the static evidence links. Browser generation and freshness updates require JavaScript.</div></noscript>
</body></html>'''


def download_card(meta, compact=False, previous=False):
    a = meta["artifact"]
    count = len(meta["validation"]["checks"])
    size = a["bytes"] / 1024 / 1024
    return f'''<section class="download-card {'compact' if compact else ''}" id="submission" data-artifact-sha256="{esc(a['sha256'])}" aria-labelledby="download-heading">
<div class="card-eyebrow"><span class="status-pill success"><span class="dot"></span> FORMAT VALIDATED</span><span class="mono">ID {esc(meta['candidate_id'])}</span></div>
<h2 id="download-heading">{'Previous candidate: Riftline.' if previous else 'Your next submission, in one click.'}</h2><p>{'Session 1 file, kept for comparison and as a fallback. Upload the Gapfinder files above first.' if previous else 'Build a single-band GeoTIFF from the new trained model. Every pixel is checked against the submission template.'}</p>
<div class="file-spec"><span>.TIF</span><div><strong>{esc(meta['arm'])}</strong><small>Float32 · EPSG:32611 · 100 m · {size:.2f} MB direct file</small></div><span class="check-circle">✓</span></div>
<button class="button primary build-button" type="button" disabled>{icon('download')} Build & download .tif <span>↗</span></button>
<div class="download-alternatives"><a href="{esc(a['file'])}" data-canonical-download download>Direct validated TIF</a><span>·</span><a href="{esc(meta['zip']['file'])}" data-canonical-download download>Single-file ZIP</a><span>·</span><a href="executive_summary.html#steps">Submission guide</a></div>
<div class="build-status" role="status" aria-live="polite">{count} format checks passed. Browser generation is loading.</div>
<div class="submission-note"><div><label for="submission-note">SUGGESTED SUBMISSION NOTE</label><button class="copy-note icon-button" aria-label="Copy submission note" title="Copy submission note">{icon('copy')}</button></div><textarea id="submission-note" rows="2" readonly>{esc(meta['note'])}</textarea></div>
<details class="file-details"><summary>File identity & verification</summary><p class="filename">{esc(a['filename'])}</p><p class="hash">Artifact SHA-256<br><code>{esc(a['sha256'])}</code></p><a href="data/submission.json">Full manifest ↗</a> · <a href="data/validation.json">Validation report ↗</a><p>Browser generation preserves the model pixels, not the original TIFF container. Its filename and container hash are shown after building. No data is uploaded; no model is trained in your browser. Rebuilding changes the file identity, not the predictions or experiment.</p></details>
<div class="card-disclaimer">{icon('verify')} <span><strong>Not yet competition-scored.</strong> Format validity is not a claim of improved accuracy.</span></div>
</section>'''


def heading(kicker, title, description, extra=""):
    return f'<div class="page-heading"><div class="eyebrow">{kicker}</div><h1>{title}</h1><p>{description}</p>{extra}</div>'


def build_home(meta, report, feed, port=None, cx=None):
    board = feed.get("leaderboard", {})
    leader, tracked = board.get("leader", {}), board.get("tracked_user") or {}
    delta = report["artifact"]["new_pixel_field"]
    strip = upload_strip(port)
    return f'''{strip}<div class="overview-heading"><div><div class="eyebrow">EXPERIMENT 003 · COVERLINE <span class="eyebrow-line"></span> COVER WHAT THE LABELS MISS</div><h1>Find the faults.<br><span>Not the ones already known.</span></h1><p>The hidden test faults are missing from the supplied labels by construction. This run derives its emission budget from the official metric itself — every emitted pixel costs 0.2 of the Tversky denominator, so a pixel has to cover ground truth that nothing else covers — then sweeps twelve support levels on a rotated spatial partition.</p></div><a class="text-link" href="executive_summary.html">Read the executive summary {icon('arrow')}</a></div>
{portfolio_section(port, "home")}
{algebra_section(cx)}
<div class="section-header section-block"><div><div class="eyebrow">PREVIOUS CANDIDATE · SESSION 1</div><h2>Riftline stays available as a fallback.</h2></div><a class="text-link" href="experiments.html">Compare on the experiments page {icon('arrow')}</a></div>
<div class="hero-grid">{download_card(meta, previous=bool(port))}<section class="map-card" aria-label="Measured prediction overview"><div class="map-title"><span class="dot"></span> GEODAWN / NEVADA & CALIFORNIA <span class="mono">UTM 11N</span></div><div class="map-view"><div class="map-grid"></div><img src="assets/prediction-preview.png" alt="Actual Riftline confidence field across the GeoDAWN footprint; brighter traces mark model predictions, not verified faults"><span class="map-north">N<br>↑</span><span class="map-coordinates">100 M GRID<br>EPSG:32611</span></div><div class="map-legend"><span><i></i> Model-predicted traces</span><span>Max-pooled preview</span></div><div class="map-caption"><h3>A new field. Not a renamed file.</h3><p>{delta['different_valid_pixels']:,} valid pixels differ from the archived ensemble ({delta['different_fraction']:.1%}). These are predictions—not confirmed discoveries.</p><a href="experiments.html">Inspect the experiment {icon('arrow')}</a></div></section></div>
<div class="metrics-row"><article><span class="metric-label">PUBLIC LEADER</span><strong data-leader-score>{score(leader.get('score'))}</strong><small><span data-leader-name>{esc(leader.get('participant', 'Unknown'))}</span> · official snapshot</small></article><article><span class="metric-label">EXTRADR19 · BEST PUBLIC</span><strong data-user-score>{score(tracked.get('score'))}</strong><small>Account-level result, not artifact-linked</small></article><article><span class="metric-label">GAPFINDER FILES</span><strong class="not-scored">Unscored<span>↗</span></strong><small>Ready for an authenticated upload</small></article><article><span class="metric-label">RIFTLINE · LOCAL UNION DTI</span><strong>{score(report['audit']['union']['dti'])}</strong><small>Different labels. Not leaderboard-comparable.</small></article></div>
<p class="snapshot-footnote">Public scores last verified <time data-board-time>{esc(board.get('verified_at','unavailable'))}</time> · <a href="{COMP}leaderboard/" target="_blank" rel="noopener noreferrer">Review official leaderboard ↗</a></p>
<section class="section-block"><div class="section-header"><div><div class="eyebrow">THE STRATEGY</div><h2>Beyond the known-fault catalogue.</h2></div><a href="research.html" class="text-link">Research & rationale {icon('arrow')}</a></div><div class="strategy-grid"><article class="strategy-card"><span class="step-num">01 / CONTEXT</span>{icon('data')}<h3>Read the landscape at three scales.</h3><p>Raw geophysics plus local relief, gradients and curvature. Test spatial patterns, not just individual pixels.</p><span class="tag">19 bands + 48 context features</span></article><article class="strategy-card"><span class="step-num">02 / UNCERTAINTY</span>{icon('research')}<h3>Unmapped does not mean absent.</h3><p>Compare cautious weighting of unlabeled pixels against a supervised control. Treat missing labels as a risk to test.</p><span class="tag">Three measured model arms</span></article><article class="strategy-card"><span class="step-num">03 / GENERALIZATION</span>{icon('verify')}<h3>Choose here. Audit somewhere else.</h3><p>Separate geographic regions for training, tuning and audit. Freeze the recipe before checking the audit labels.</p><span class="tag">51.2 km blocks · 3.2 km buffer</span></article></div></section>
<section class="bottom-grid"><div class="feed-panel"><div class="section-header"><h2>Evidence feed</h2><span class="small-label">SNAPSHOT, NOT STREAMING</span></div><div id="feed-items"><div class="feed-row"><span class="feed-marker"></span><div><strong>Primary sources and rule checks</strong><p>{len(feed['sources'])} monitored sources. Last-success timestamps are preserved when a refresh fails.</p></div></div><div class="feed-row"><span class="feed-marker"></span><div><strong>Candidate generated and locally validated</strong><p>{esc(report['completed_at'])} · real rasters, real model, complete read-back.</p></div></div></div><a href="sources.html#feed" class="text-link">View source health & alerts {icon('arrow')}</a></div><div class="next-panel"><span class="eyebrow">THE NEXT DECISION</span><h2>Measure the new candidate.<br>Don’t assume the gain.</h2><p>The target is to beat the public lead. The next credible signal is a scored upload, followed by rotated spatial tests and a high-resolution terrain pilot.</p><a href="executive_summary.html#steps" class="button secondary">How to submit {icon('arrow')}</a></div></section>'''



def deployment_notice(report):
    d = report["deployment"]
    cap = report["config"]["max_emitted_fraction"]
    if d["refit_passed_support_gate"]:
        return (f'<p><strong>Deployment:</strong> the frozen all-data refit passed the {cap:.0%} support cap '
                f'with {d["published_support_fraction"]:.2%} support. Its hidden-label accuracy is unmeasured; '
                'the audit scores refer to the holdout-trained model.</p>')
    folds = report["partition"]["training_folds"]
    return (f'<p><strong>Deployment guard:</strong> the all-data refit emitted {d["refit_support_fraction"]:.2%} '
            f'against a {cap:.0%} cap and was rejected. The unchanged tuning-selected model, trained on '
            f'folds {esc(folds)}, is published with {d["published_support_fraction"]:.2%} support instead. '
            'The fallback was introduced after the original density failure, not pre-registered before '
            'that first attempt. No arm, threshold or cap was changed using the audit labels. '
            '<a href="data/experiment.json">Measured deployment record ↗</a></p>')


def build_summary(meta, report, port=None, gx=None, cx=None):
    return heading("EXECUTIVE SUMMARY", "From a tested file<br>to a real submission.", "Download file 1, upload it, paste its Note. Below: why these files, what is still unknown, and what a successful download does not prove.") + f'''
{portfolio_section(port, "summary")}{coverage_summary(cx)}{gapfinder_summary(port, gx)}
<div class="section-header section-block"><div><div class="eyebrow">PREVIOUS CANDIDATE · SESSION 1</div><h2>Riftline: kept as a fallback.</h2></div></div>
<div class="summary-grid">{download_card(meta, True, previous=bool(port))}<div class="summary-side"><div class="status-pill neutral-pill">SESSION 1 OUTCOME</div><h2>A distinct candidate.<br>An unknown public score.</h2><p>The CPU experiment compared three arms. <strong>{esc(meta['arm'])}</strong> was selected on the tuning fold; its recipe was frozen before spatial audit.</p>{deployment_notice(report)}<p>We have not uploaded this candidate to DrivenData and do not have its competition score. Account-level leaderboard changes are never automatically assigned to this file.</p><div class="callout">The old data-placement blocker is resolved. No GPU, paid data source or local install is needed to download this artifact.</div><a href="experiments.html" class="text-link">Read the measured results {icon('arrow')}</a></div></div>
<section id="steps" class="section-block"><div class="eyebrow">THE HANDOFF</div><h2>Submit in six steps.</h2><div class="steps-list">
<article><span>1</span><div><h3>Confirm eligibility and competition enrollment.</h3><p>Open the <a href="{COMP}" target="_blank" rel="noopener noreferrer">official competition</a>, sign in to your DrivenData account and enroll. Review <a href="{RULES}">rules §1.3 and §3.1</a>. We cannot make legal attestations or authenticate as you.</p></div></article>
<article><span>2</span><div><h3>Click “Download .tif” on card 1 at the top of this page (or on the strip above).</h3><p>Every published file is re-read and checked against the pinned template before publishing (CRS, transform, shape, float32, NaN exactly outside the mask, finite values in [0, 1] inside). Use the next card’s file for your next upload. Do not upload this web page, a PDF, or an evidence JSON.</p></div></article>
<article><span>3</span><div><h3>In DrivenData, choose Submit → Make new submission.</h3><p>Under <strong>File to submit</strong>, choose the downloaded <code>.tif</code>. The form also permits a ZIP containing one GeoTIFF; the supplied ZIP contains exactly one file. The TIF is the simplest path. Do not upload an outer GitHub Actions artifact ZIP, which also contains reports and model files.</p></div></article>
<article><span>4</span><div><h3>Paste that file’s Note.</h3><p>Use the Copy button on the same card. Each Note names the variant, model policy and the first 10 hex characters of the file’s SHA-256. You can match a leaderboard entry to a file later. Keep the filename and hash with the result.</p></div></article>
<article><span>5</span><div><h3>Submit, then read the platform response.</h3><p>A local pass is not a platform acceptance or an accuracy guarantee. If rejected, retain the exact filename and message. If accepted, keep the submission ID and public score to link the result to this candidate.</p></div></article>
<article><span>6</span><div><h3>Respect the quota and choose one final submission.</h3><p><a href="{RULES}">Rules §3.2–3.6</a> specify three uploads per week and one final selection for both rounds. Finalists must provide reproducible code and documentation; disclose generative-AI assistance in the narrative.</p></div></article></div></section>
<section id="rejection" class="section-block"><div class="eyebrow">IF AN UPLOAD IS REJECTED</div><h2>“Predicted values must be in range [0, 1]”</h2><div class="two-column"><div><p>This can mean out-of-range numbers, infinity, or NaN inside the template-valid region. An apparently correct min/max is not enough: reductions can ignore NaN.</p><p>The feature footprint differs from the required template footprint; using it as the output mask can leave invalid values. This does not identify which exact file you previously uploaded. This pipeline predicts every template-valid pixel and verifies the exact mask after writing. Outside pixels must be NaN; inside pixels must be finite and bounded. No blind global <code>nan_to_num</code> or silent exporter clipping.</p></div><div class="code-panel"><span>INDEPENDENT LOCAL CHECK</span><pre><code>python scripts/validate_submission.py \
  your-downloaded-file.tif \
  --report evidence/upload-check.json</code></pre><p>Exit 0 = documented-format pass. Nonzero = do not upload. Review the <a href="data/validation.json">current report</a> or <a href="verification.html">all verification gates</a>.</p></div></div></section>
<div class="warning-box"><strong>Deadline wording needs attention.</strong> The <a href="{COMP}">competition website</a> currently lists December 3, 2026, 23:59 UTC. Rules §1.2 directs entrants to the website for the current timeline, while Appendix A also contains a generic 5 p.m. ET clause and document-format wording. Predictions are a GeoTIFF per the specific submission section. Review both sources and clarify any ambiguity with the organizers well before the deadline; we do not invent a legal interpretation.</div>'''


def build_experiments(meta, report, gx=None, v1=None, diag=None, cx=None):
    rows = []
    for arm in report["arms"]:
        name = arm["arm"]["id"]
        picked = name == report["selected"]["arm"]
        selected_tag = '<span class="tag">Selected on tuning</span>' if picked else ""
        rows.append(f'<tr class="{"selected-row" if picked else ""}"><td><strong>{esc(name)}</strong>{selected_tag}</td><td>{"67" if arm["arm"]["context"] else "19"}</td><td>{arm["arm"]["unlabeled_weight"]}</td><td>{score(arm["best_tuning_policy"]["tuning"]["dti"])}</td><td>{score(arm["audit"]["known"]["dti"])}</td><td>{score(arm["audit"]["proxy_only"]["dti"])}</td><td>{score(arm["audit"]["union"]["dti"])}</td></tr>')
    p = report["partition"]
    return heading("EXPERIMENT LOG", "A hypothesis is not a result.", "Executed arms, pre-registered selection rules, frozen before audit. Every local number below is a published-catalogue surrogate—not a hidden-label or leaderboard score.") + coverage_experiment_section(cx, gx) + experiment_section(gx, v1, diag) + f'''
<div class="section-header section-block"><div><div class="eyebrow">EXPERIMENT 001 · PREVIOUS</div><h2>Riftline context-distance</h2></div></div>
<div class="run-banner"><div><span class="status-pill success">COMPLETED</span><strong>{esc(report['strategy'])}</strong><small>{esc(report['completed_at'])}</small></div><a href="data/experiment.json" class="text-link">Full experiment JSON {icon('external')}</a></div>
<div class="warning-box">{deployment_notice(report)}<p>The repeated fixed-fold audit is diagnostic, not a fresh independent replication. The original run’s selected context field was bit-identical across its two executions; its raw-feature control was not. See <a href="../evidence/repeatability.json">the dated repeatability record</a>, which does not certify every future retraining run.</p></div><section class="section-block"><div class="section-header"><h2>The controlled comparison</h2><span class="tag">Same samples · same spatial split</span></div><div class="table-scroll"><table><caption>Each arm’s policy is chosen on the tuning region. Audit scores do not choose the winner.</caption><thead><tr><th>Model arm</th><th>Features</th><th>Unlabeled weight</th><th>Tune · union</th><th>Audit · known</th><th>Audit · proxy</th><th>Audit · union</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p class="table-note">Known = supplied training catalogue in unseen geography. Proxy = inherited SGMC code-2 faults, absent within 300 m of known labels. Union = recomputed metric on both populations, not an average of their scores. None is the private expert dataset.</p></section>
<div class="two-column"><section class="white-card"><span class="eyebrow">FROZEN POLICY</span><h2>{esc(report['selected']['arm'])}</h2><dl class="fact-list"><dt>Emission</dt><dd>{esc(report['selected']['emission'])}</dd><dt>Confidence floor</dt><dd>{report['selected']['floor']}</dd><dt>Seed</dt><dd>{report['config']['seed']}</dd><dt>Candidate policies evaluated</dt><dd>{len(report['candidates'])}</dd><dt>Training runtime</dt><dd>{report['seconds']/60:.1f} min · CPU</dd><dt>Public score</dt><dd>Unknown · no upload performed</dd></dl><p class="hash">Frozen selection SHA-256<br><code>{esc(report['selection_frozen_sha256'])}</code></p></section><section class="white-card"><span class="eyebrow">SPATIAL AUDIT</span><h2>No random-pixel shortcut.</h2><dl class="fact-list"><dt>Block size / interior buffer</dt><dd>{p['block_px']*0.1:g} km / {p['buffer_px']*0.1:g} km</dd><dt>Training folds</dt><dd>{esc(p['training_folds'])}</dd><dt>Tuning fold</dt><dd>{p['tuning_fold']}</dd><dt>Untouched audit fold</dt><dd>{p['audit_fold']}</dd><dt>Audit area</dt><dd>{p['audit_pixels']:,} pixels</dd><dt>Audit blocks with valid area</dt><dd>{len(report['audit_blocks'])}</dd></dl><p>Only one fixed split has been run. Spatial units are limited. The 32-pixel guard covers the 30-pixel feature radius, but does not fully separate all feature-plus-postprocessing support; this is not proof of complete statistical independence. We do not present a precise confidence interval or a claimed statistical win from this experiment.</p></section></div>
<section class="section-block"><h2>What actually makes this different?</h2><div class="comparison-list"><div><span>Target</span><p>Regress a 300 m triangular proximity field from known labels, not the inherited hard-label ensemble.</p></div><div><span>Context</span><p>Test multiscale, mask-aware relief and curvature features without injecting coordinates or catalogue values as inputs.</p></div><div><span>Geometry</span><p>Extract ridges along their local Hessian normal. Compare soft and binary confidence emissions on tuning data.</p></div><div><span>Proof</span><p>{report['artifact']['new_pixel_field']['different_valid_pixels']:,} valid pixels differ from the archived artifact. The filename alone is not evidence of a new strategy.</p></div></div></section>
<section class="section-block"><h2>Limits that can change the conclusion</h2><ul class="limitation-list">{''.join(f'<li>{esc(x)}</li>' for x in report['limitations'])}</ul><a class="text-link" href="research.html">Next experiments, ordered by evidence value {icon('arrow')}</a></section>'''


def build_sources(data, sources, feed):
    records = {s["id"]: s for s in feed["sources"]}
    rows = []
    for s in sources["sources"]:
        r = records.get(s["id"], {})
        rows.append(f'<tr data-source-kind="{esc(s["kind"])}"><td><strong>{esc(s["title"])}</strong><small>{esc(s["publisher"])}</small></td><td>{esc(s["role"])}</td><td>{esc(s["access"])}<small>{esc(s["license"])}</small></td><td>{esc(s["used"])}</td><td><span class="source-health" data-source-id="{esc(s["id"])}">{esc(r.get("status", "not checked"))}</span><small>{esc(r.get("last_verified_at", "Unavailable"))}</small></td><td><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">Source ↗</a></td></tr>')
    bands = ''.join(f'<tr><td class="mono">{b["band"]:02d}</td><td><strong>{esc(b["name"])}</strong></td><td>{esc(b["embedded_description"])}</td><td>{b["valid_pixels"]:,}</td><td>{b["missing_inside_template"]:,}</td></tr>' for b in data["bands"])
    claims = ''.join(f'<tr><td><code>{esc(c["id"])}</code></td><td>{esc(c["statement"])}</td><td><q>{esc(c["quote"])}</q></td><td><a href="{esc(s["url"])}">{esc(s["publisher"])} ↗</a></td></tr>' for s in sources["sources"] for c in s["claims"])
    return heading("DATA & SOURCE REGISTER", "Nothing important without a trail.", "Official sources, measured input files, quoted requirements and explicit access limits. Search the register or download it for your own audit.") + f'''
<section id="feed" class="feed-panel full-width"><div class="section-header"><div><h2>Source health</h2><p id="feed-summary">Last successful evidence is retained if a refresh fails.</p></div><button class="button secondary" id="refresh-feed" type="button">Refresh snapshot ↻</button></div><div id="feed-alerts" aria-live="polite"></div><p class="table-note">GitHub Actions is configured to check every six hours. This button reloads the published JSON; it does not scrape sources or trigger a model run. GitHub schedules can be delayed or disabled. Each source has its own last-success time.</p><a href="data/feed.json">Raw dated feed ↗</a></section>
<section class="section-block"><div class="section-header"><h2>The active source register</h2><a href="data/source-catalog.csv" download class="text-link">Download CSV {icon('download')}</a></div><div class="table-tools"><label class="search-box">{icon('research')}<input id="source-search" type="search" placeholder="Search source, license, use…" aria-label="Search source register"></label><div class="filters" aria-label="Filter source type"><button class="filter active" data-filter="all" aria-pressed="true">All</button><button class="filter" data-filter="official" aria-pressed="false">Official sources</button><button class="filter" data-filter="primary-paper" aria-pressed="false">Scientific papers</button></div><span id="source-count">{len(rows)} sources</span></div><div class="table-scroll"><table id="source-table"><caption>Curated active sources; not an exhaustive catalogue of all possible external data.</caption><thead><tr><th>Source / publisher</th><th>Role</th><th>Access / rights</th><th>Used here?</th><th>Last verification</th><th>Review</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section class="section-block"><div class="section-header"><div><div class="eyebrow">MEASURED INPUTS</div><h2>The 19-band inventory</h2></div><a href="data/data-inventory.json" class="text-link">Hashes & measurement JSON {icon('external')}</a></div><p>Grid {data['width']:,} × {data['height']:,} · {data['crs']} · {data['valid_pixels']:,} template-valid pixels · {data['known_fault_pixels']:,} known positives. Byte hashes match the inherited mirror inventory; they are not new authenticated checksums from DrivenData.</p><div class="warning-box"><strong>Two important mismatches.</strong> The supplied sample contains {data['template_positive_pixels']:,} positive values despite the official all-absence description. {data['feature_missing_inside_template']:,} template-valid pixels have no finite feature band, and {data['feature_present_outside_template']:,} feature pixels sit outside the template. Use the template mask, not the feature footprint. Embedded band meanings—particularly <code>tc</code>—are not independently certified geological interpretations.</div><div class="table-scroll"><table><caption>Descriptions below are quoted embedded metadata, not newly inferred facts.</caption><thead><tr><th>Band</th><th>Identifier</th><th>Embedded description</th><th>Finite pixels</th><th>Missing inside mask</th></tr></thead><tbody>{bands}</tbody></table></div></section>
<section class="section-block"><h2>Claim-by-claim review</h2><p>Automation tests the presence of these normalized quotes. A changed or unavailable source is flagged; retrieval alone does not verify a broader interpretation. The initial evidence was read through the research tool; raw HTTP hashes are recorded only when the scheduled fetch obtains bytes.</p><div class="table-scroll"><table><thead><tr><th>Claim ID</th><th>Working statement</th><th>Supporting source excerpt</th><th>Primary source</th></tr></thead><tbody>{claims}</tbody></table></div></section>
<div class="callout"><strong>Preserved, not re-certified:</strong> the original <a href="../legacy/docs/data_catalog.json">larger source catalogue</a> and <a href="../legacy/data/dem_links.json">DEM URL index</a> are available for audit. Their historical checks are not current checks of every URL. No 1 m DEM tile is used in this artifact.</div>'''


def build_research(report):
    return heading("RESEARCH LOG", "Better questions.<br>Falsifiable experiments.", "The aim is genuine fault discovery. Each proposed upgrade has a rationale, a test and a reason it could fail—not a promised score.") + clarifications_section() + f'''
<section class="research-grid"><article class="white-card"><span class="eyebrow">01 / INCOMPLETE LABELS</span><h2>Lower confidence in “negative.”</h2><p>Hermant et al. retains fault-bearing tiles partly to reduce observation bias. We test lower weights on unmapped pixels rather than assuming verified absence.</p><div class="tag">Implemented: unlabeled weight 0.25 vs 1.0</div><p class="small">This is heuristic PU-inspired weighting. It does not implement a non-negative PU risk estimator or establish missing-at-random assumptions.</p><a href="https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf" class="text-link">Hermant et al., 2025 ↗</a></article>
<article class="white-card"><span class="eyebrow">02 / SPATIAL DEPENDENCE</span><h2>Make the audit geographically different.</h2><p>Roberts et al. explains why random cross-validation can understate error for structured data, and why the blocking strategy matters.</p><div class="tag">Implemented: disjoint, buffered spatial regions</div><p class="small">One split is not enough. Rotate the folds and evaluate source-held-out catalogues before asserting robust superiority.</p><a href="https://doi.org/10.1111/ecog.02881" class="text-link">Roberts et al., 2017 ↗</a></article>
<article class="white-card"><span class="eyebrow">03 / RESOLUTION</span><h2>Look for scarps, not upsampled pixels.</h2><p>USGS 3DEP offers publicly available terrain data. A bounded 10 m derivative pilot is a rational next test for structures lost at 100 m.</p><div class="tag amber">Queued: high-resolution DEM pilot</div><p class="small">Not used in the current model. Verify tile coverage, datum and nodata; separate real lidar detail from interpolation artifacts.</p><a href="https://www.usgs.gov/3d-elevation-program/about-3dep-products-services" class="text-link">USGS 3DEP source & rights ↗</a></article>
<article class="white-card"><span class="eyebrow">04 / SOURCE INDEPENDENCE</span><h2>Don’t learn the answer key.</h2><p>Gapfinder trains on SGMC in training regions and scores on SGMC in other regions. Geography helps, but it does not remove source circularity. v1 showed this: its SGMC-trained pick scored poorly on held-out <em>supplied</em> faults.</p><div class="tag">Implemented in v2: selection also requires held-out supplied-fault skill</div><p class="small">Riftline never trained on SGMC. A third, fully independent fault source for auditing is still outstanding.</p><a href="../legacy/data/evidence/pseudo_labels/pooled_two_population_contrast.json" class="text-link">Read the inherited limitation ↗</a></article></section>
<section class="section-block"><div class="section-header"><h2>Continue the previous work—without repeating it.</h2><a href="../NEXT_STEPS.md" class="text-link">Full next-session plan {icon('arrow')}</a></div><div class="roadmap"><article><span class="status-pill success">DONE HERE</span><div><h3>Place the data, generate a different artifact, make it easy to submit.</h3><p>Hash-pinned restoration, an executed CPU experiment, strict mask/range gates, prominent browser TIF generation and a short identifying Note.</p></div></article><article><span class="status-pill neutral-pill">NEXT SIGNAL</span><div><h3>Associate a scored upload with this exact file.</h3><p>Requires the enrolled DrivenData account. Keep the artifact/build hash and platform submission ID; the public account’s best score alone cannot prove an improvement.</p></div></article><article><span class="status-pill neutral-pill">NEXT TEST</span><div><h3>Rotate folds and complete independent-source controls.</h3><p>Retain the frozen candidate set, measure paired spatial effects, and resolve missing historical pseudo-label folds 2 and 3 before making pooled claims.</p></div></article><article><span class="status-pill neutral-pill">NEXT INPUT</span><div><h3>Run the small DEM pilot before spending GPU time.</h3><p>Measure whether extra terrain detail helps on held-out geographies. Use those results to justify any patch-model or GPU-scale expansion.</p></div></article></div></section>
<div class="two-column"><div class="callout"><strong>Read the bounded literature review.</strong><p>Includes official target/metric analysis, implemented hypotheses, risks, data rights, a PU theory reference and the organizer-recommended Mattéo paper. It is not an exhaustive scientific review.</p><a href="../research/RESEARCH.md">Full research ledger ↗</a></div><div class="callout"><strong>Own the outcome.</strong><p>The goal is a competitive solution, not a good-looking local metric. Publish negative results, keep data and artifact identities stable, and never turn an unmeasured hypothesis into a score claim.</p><a href="../README.md">Original project brief & values ↗</a></div></div>'''


def build_verification(meta, report, review, port=None):
    current = {meta["artifact"]["sha256"]}
    if port and port.get("items"):
        current.add(port["items"][0]["sha256"])  # the live portfolio owns the current release
    if review.get("artifact_sha256") not in current:
        review = {}  # Past release reviews are not automatically inherited by a new model.
    gates = ''.join(f'<tr><td><span class="status-pill {"success" if c["passed"] else "warning"}">{"PASS" if c["passed"] else "FAIL"}</span></td><td>{esc(c["check"])}</td><td class="wrap-anywhere">{esc(c["detail"])}</td></tr>' for c in meta["validation"]["checks"])
    passes = ''.join(f'<article class="white-card"><span class="eyebrow">PASS {p["pass"]}</span><h2>{esc(p["title"])}</h2><p>{esc(p["summary"])}</p><span class="tag">{esc(p["status"])}</span></article>' for p in review.get("passes", []))
    return heading("VERIFICATION", "Trust the bytes.<br>Question the claims.", "The documented format is machine-checked. Accuracy on hidden labels is not. These are deliberately separate states.") + f'''
<div class="verification-summary"><div>{icon('verify')}<strong>Format gate passed</strong><span>{len(meta['validation']['checks'])} checks · {esc(meta['validation']['checked_at'])}</span></div><a href="data/validation.json" class="button secondary">Read the raw report {icon('external')}</a></div>
{portfolio_verification(port)}<section class="section-block"><div class="section-header"><div><div class="eyebrow">RIFTLINE · PREVIOUS CANDIDATE</div></div></div><div class="table-scroll"><table><caption>Read-back of the published Riftline artifact against the hash-pinned supplied template.</caption><thead><tr><th>Gate</th><th>Requirement</th><th>Measured detail</th></tr></thead><tbody>{gates}</tbody></table></div></section>
<div class="two-column"><section class="white-card"><span class="eyebrow">BROWSER PATH</span><h2>Built here. Re-read here.</h2><p>The browser verifies compressed and raw field hashes, checks every value against an independently packaged template mask, writes the TIFF, reads its own bytes and checks the decoded pixel hash again.</p><p>Node runs the exact same JavaScript in automated tests; Rasterio independently reads the generated TIFF. A failed check prevents browser download.</p><a href="data/browser-validation.json">Executed browser-writer evidence ↗</a></section><section class="white-card"><span class="eyebrow">PROVENANCE</span><h2>Original project, safely preserved.</h2><p>All 387 imported files matched their pinned upstream Git blob IDs. The full source snapshot lives under <code>legacy/</code>, with large feature parts restored externally rather than recommitted.</p><p>Historical source claims and workflow runs remain historical. The new artifact is measured against the old pixel field; we cannot equate the old file with extradr19’s submission ID.</p><a href="../provenance/import.json">Import verification ↗</a> · <a href="../THIRD_PARTY.md">Attribution & AI disclosure ↗</a></section></div>
<section class="section-block"><div class="section-header"><h2>Three-pass review</h2><a href="../evidence/review.json" class="text-link">Review evidence {icon('external')}</a></div><div class="strategy-grid">{passes or '<div class="warning-box">Review still in progress. No completed-pass claim is made yet.</div>'}</div></section>
<section class="section-block"><h2>Reproduce on a CPU</h2><div class="code-panel"><pre><code>python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
bash scripts/download_competition_data.sh
python scripts/prepare_data.py
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m gems3.train
python -m gems3.publish
python -m gems3.site
python -m pytest</code></pre></div><p>The full model/cache files stay outside Git. The report records model hash, source inputs, config, package versions, sample indices and frozen selection hash. <a href="data/experiment.json">Inspect the manifest</a> before trusting a reproduced number.</p></section>
<div class="warning-box"><strong>Cannot be verified here:</strong> hidden-label accuracy, a higher competition score, account eligibility, authenticated upload or final prize ranking. Official-host network restrictions and changed source text are surfaced in the source feed, not replaced with made-up current facts.</div>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", type=Path, default=ROOT / "docs")
    args = ap.parse_args()
    docs = args.docs
    meta = read_json(docs / "data/submission.json")
    report = read_json(docs / "data/experiment.json")
    data = read_json(docs / "data/data-inventory.json")
    sources = read_json(ROOT / "research/sources.json")
    feed = read_json(docs / "data/feed.json")
    review = read_json(ROOT / "evidence/review.json") if (ROOT / "evidence/review.json").exists() else {}
    port = load_optional(docs / "data/portfolio.json")
    gx = load_optional(docs / "data/gapfinder-experiment.json")
    cx = load_optional(docs / "data/coverage-experiment.json")
    v1 = load_optional(ROOT / "evidence/gapfinder-v1-experiment.json")
    diag = load_optional(ROOT / "evidence/gapfinder-diagnostics.json")
    pages = [("index.html", "Mission control", build_home(meta, report, feed, port, cx)),
             ("executive_summary.html", "Executive summary", build_summary(meta, report, port, gx, cx)),
             ("experiments.html", "Experiments", build_experiments(meta, report, gx, v1, diag, cx)),
             ("sources.html", "Data & sources", build_sources(data, sources, feed)),
             ("research.html", "Research log", build_research(report)),
             ("verification.html", "Verification", build_verification(meta, report, review, port))]
    for filename, title, body in pages:
        (docs / filename).write_text(shell(filename, title, body), encoding="utf-8")
    print(f"Rendered {len(pages)} evidence-backed pages")


if __name__ == "__main__":
    main()
