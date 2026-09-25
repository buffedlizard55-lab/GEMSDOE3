"""Pindrop v4 site sections: the placement algebra, the measured layer comparison, the rotated audit.

Every number is read from docs/data/pindrop-experiment.json (written by gems3.pindrop and re-hashed by
gems3.pindrop_publish) or from the published portfolio manifest. Nothing is typed by hand, and no
local proxy number is presented as a competition score.
"""
from __future__ import annotations

from .site_gapfinder import SUBMIT_URL, esc


def _pct(value) -> str:
    return "—" if value is None else f"{value:.2%}"


def _num(value, digits=3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def upload_strip(port: dict | None) -> str:
    """The one-screen answer to 'what do I upload?', rendered above everything else on the site.

    The order is the manifest's order, which the publisher sets by value rather than by experiment
    number: the control file is published last and carries its own badge, so nothing on the strip
    implies that a deliberately weaker file should be sent before a stronger one.
    """
    if not port:
        return ""
    items = port["items"]
    cards = ""
    for i in items:
        role = i.get("role", "primary")
        marker = ("" if role == "primary" else f'<span class="tag amber">{esc(i["badge"])}</span>')
        cards += (
            f'<a class="strip-step" data-role="{esc(role)}" href="{esc(i["file"])}" '
            f'download="{esc(i["filename"])}">'
            f'<span class="strip-order">{i["order"]}</span><span><strong>{esc(i["title"])}</strong>'
            f'{marker}<small>{i["emitted_pixels"]:,} pixels · {i["checks_passed"]}/{i["checks_total"]} '
            f'format gates · {i["bytes"] / 1024 / 1024:.2f} MB</small></span></a>')
    first = items[0]
    return f'''<section class="upload-strip" id="submit-now" aria-label="Upload order">
<div class="strip-head"><span class="status-pill success"><span class="dot"></span> READY TO SUBMIT</span>
<strong>Download → upload → paste the Note.</strong>
<span class="strip-note">Three files, in this order. Card 1 is the measured best; card 2 is a second,
independently trained system; card 3 is the dense control, published so the placement hypothesis can be
tested on the real leaderboard rather than assumed. No account data, no modelling and no install needed:
every file is re-validated and re-hashed before publishing.</span></div>
<div class="strip-grid">{cards}</div>
<div class="strip-foot">Start with <strong>{esc(first["title"])}</strong>
(<a href="{esc(first["file"])}" download="{esc(first["filename"])}">direct .tif</a> ·
<a href="{esc(first["zip"])}" download>single-file ZIP</a>) and paste
<code>{esc(first["note"])}</code>. Full instructions in the
<a href="executive_summary.html#steps">executive summary</a> or
<a href="{SUBMIT_URL}" target="_blank" rel="noopener noreferrer">DrivenData → Submissions ↗</a>.</div>
</section>'''


def nodes_section(pt: dict | None) -> str:
    """Why the published emission is a spaced node schedule, with the measured comparison table."""
    if not pt:
        return ""
    alg = pt["metric_algebra"]
    sel = pt["selected"]
    rows = ""
    for row in pt["layer_comparison_tuning"]:
        cells = ""
        for key in ("ridge@1", "nodes@4", "nodes@5"):
            block = row.get(key)
            cells += ("<td>—</td><td>—</td>" if not block else
                      f'<td>{_num(block["gap_dti"], 4)}</td><td>{_num(block["credit_per_emitted_pixel"], 4)}</td>')
        rows += f'<tr><td>{row["budget"]:.4%}</td>{cells}</tr>'
    spans = ""
    for entry in pt.get("schedules", [])[:24]:
        if entry["arm"] != sel["arm"]:
            continue
        spans += (f'<tr><td>{esc(entry["arm"])}</td><td>{esc(entry["layer"])}</td><td>{entry["spacing"]}</td>'
                  f'<td>{entry["halo"]}</td><td>{entry["tip"]}</td><td>{entry["accepted_nodes"]:,}</td>'
                  f'<td>{_num(entry["min_chebyshev"], 1)}</td><td>{_num(entry["min_euclidean"], 2)}</td></tr>')
    return f'''<section class="section-block" id="algebra">
<div class="section-header"><div><div class="eyebrow">WHY THIS DESIGN</div>
<h2>Placement beats mass.</h2></div>
<a href="data/pindrop-experiment.json" class="text-link">Raw experiment JSON ↗</a></div>
<div class="two-column"><div>
<p>The official metric credits a truth pixel from the <em>single best</em> prediction inside a 300 m
triangular kernel, and charges every prediction pixel {alg["pixel_denominator_cost"]} × (1 − k) when it
is not near truth. So two predictions four pixels apart along the same trace cover nearly the same
truth while both paying the full false-positive weight. The metric is a coverage function with a
pixel budget — and the cheapest optimal set is a <strong>spaced schedule of nodes</strong>, not a
continuous line.</p>
<div class="code-panel"><pre><code>kernel radius R = {alg["kernel_radius_px"]} px (300 m at 100 m pixels)
largest spacing that cannot lose coverage at the midpoint:
    spacing / 2 &lt; R  →  spacing ≤ {alg["max_safe_spacing_px"]} px
published spacing = {sel["spacing"]} px → worst-case gap to a node = {alg["coverage_half_gap_px_for_published_spacing"]:.1f} px &lt; {alg["kernel_radius_px"]}</code></pre></div>
<p>The implementation is one code path: rank every candidate pixel by model confidence, then accept a
pixel only when no accepted node lies inside a suppression square of half-width
<span class="mono">spacing − 1</span>. <span class="mono">spacing = 1</span> suppresses nothing, so the
control layer is exactly the dense ridge prefix that a confidence floor would emit. The only changed
parameter between the published file and its control is that number.</p>
<p>This is a metric-aware encoding of a fault trace, not a claim that faults are dotted in reality and
not a calibrated probability. The dense control is published beside it so the choice can be tested on
the leaderboard instead of assumed.</p>
</div><div>
<dl class="fact-list"><dt>Pixel denominator cost</dt><dd>{alg["pixel_denominator_cost"]}</dd>
<dt>Kernel radius</dt><dd>{alg["kernel_radius_px"]} px (300 m)</dd>
<dt>Maximum safe spacing</dt><dd>{alg["max_safe_spacing_px"]} px</dd>
<dt>Published layer</dt><dd>{esc(sel["layer"])} k={sel["spacing"]}</dd>
<dt>Budgets swept</dt><dd>{len({c["budget"] for c in pt["candidates"]})}</dd>
<dt>Candidate policies evaluated</dt><dd>{len(pt["candidates"])}</dd></dl>
<p class="small">Candidates are oriented-ridge pixels outside the supplied labels; tip-extension rays
enter the same budget as candidates ranked by the confidence of the tip that generated them. Supplied-label
proxy scoring excludes ray pixels for both layers, because a ray starts one pixel beyond a supplied trace.</p>
</div></div>
<div class="table-scroll"><table><caption>Measured on the tuning fold at <em>identical emitted-pixel
budgets</em> (the evidence for the placement claim). Gap DTI is the public SGMC-gap proxy; credit per
emitted pixel = added TP<sub>w</sub> ÷ emitted pixels.</caption>
<thead><tr><th rowspan="2">Budget</th><th colspan="2">Dense ridge k=1</th><th colspan="2">Nodes k=4</th>
<th colspan="2">Nodes k=5</th></tr><tr><th>Gap DTI</th><th>Credit/px</th><th>Gap DTI</th><th>Credit/px</th>
<th>Gap DTI</th><th>Credit/px</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="table-scroll"><table><caption>Accepted nodes and the measured minimum separation of the
{esc(sel["arm"])} schedules.</caption><thead><tr><th>Arm</th><th>Layer</th><th>k</th><th>Halo</th>
<th>Tip</th><th>Accepted nodes</th><th>Min Chebyshev</th><th>Min Euclidean</th></tr></thead>
<tbody>{spans}</tbody></table></div>
<p class="table-note">Where a budget exceeds the supply of admissible nodes, the schedule simply ends;
those rows are duplicates of the largest feasible schedule and are labelled by their measured emitted
fraction, not by the requested budget.</p></section>'''


def experiment_section(pt: dict | None) -> str:
    if not pt:
        return ""
    sel = pt["selected"]
    part = pt["partition"]
    tag = ' <span class="tag">Selected</span>'
    arms = "".join(
        f'<tr><td><strong>{esc(a["arm"]["id"])}</strong>'
        f'{tag if a["arm"]["id"] == sel["arm"] else ""}</td>'
        f'<td>{esc(a["objective"])}</td><td>{a["seconds"] / 60:.1f} min</td>'
        f'<td>{_pct(a["best"]["emitted_fraction"]) if a["best"] else "—"}</td>'
        f'<td>{_num(a["best"]["robust_dti"], 4) if a["best"] else "—"}</td></tr>' for a in pt["arms"])
    audit = "".join(
        f'<tr><td>{esc(row["arm"])}</td><td>{esc(row["role"])}</td>'
        f'<td class="mono wrap-anywhere">{esc(row["policy"]["layer"])} k={row["policy"]["spacing"]} '
        f'b={row["policy"]["budget"]:.4f} h={row["policy"]["halo"]} L={row["policy"]["tip"]}</td>'
        f'<td>{_pct(row["emitted_fraction"])}</td><td>{_num(row["audit"]["gap"]["dti"], 4)}</td>'
        f'<td>{_num(row["audit"]["all"]["dti"], 4)}</td><td>{_num(row["audit"]["known"]["dti"], 4)}</td>'
        f'<td>{_num(row["audit"]["far"]["dti"], 4)}</td></tr>' for row in pt["audit"])
    refs = "".join(
        f'<tr><td>{esc(label)}</td><td class="mono wrap-anywhere">{esc(entry["file"])[:40]}</td>'
        f'<td>{_num(entry["tune"]["gap"]["dti"], 4)}</td><td>{_num(entry["tune"]["all"]["dti"], 4)}</td>'
        f'<td>{_num(entry["tune"]["known"]["dti"], 4)}</td><td>{_num(entry["audit"]["gap"]["dti"], 4)}</td>'
        f'<td>{_num(entry["audit"]["all"]["dti"], 4)}</td><td>{_num(entry["audit"]["known"]["dti"], 4)}</td>'
        f'</tr>' for label, entry in pt["references"].items())
    boots = "".join(
        f'<tr><td>{esc(label)}</td><td>{_num(v["gap"]["observed_difference"], 4)}</td>'
        f'<td class="mono">[{_num(v["gap"]["ci95"][0], 3)}, {_num(v["gap"]["ci95"][1], 3)}]</td>'
        f'<td>{_num(v["all"]["observed_difference"], 4)}</td>'
        f'<td class="mono">[{_num(v["all"]["ci95"][0], 3)}, {_num(v["all"]["ci95"][1], 3)}]</td></tr>'
        for label, v in pt["audit_bootstrap"].items())
    tranche = "".join(
        f'<tr><td>{r["budget"]:.4%}</td><td>{_pct(r["emitted_fraction"])}</td><td>{_num(r["dti"], 4)}</td>'
        f'<td>{r["added_pixels"]:,}</td><td>{_num(r["added_TP_w"], 2)}</td><td>{_num(r["added_FP_w"], 2)}</td>'
        f'<td>{_num(r["covered_credit_per_added_pixel"], 4)}</td>'
        f'<td>{_num(r["break_even_credit_per_pixel"], 4)}</td></tr>' for r in pt["tranche_tuning"])
    lims = "".join(f"<li>{esc(text)}</li>" for text in pt["limitations"])
    dep = pt["deployment"]
    return f'''<section class="section-block" id="pindrop">
<div class="section-header"><div><div class="eyebrow">EXPERIMENT 004 · PINDROP</div>
<h2>A fixed pixel budget, placed at the kernel's own spacing.</h2></div>
<a href="data/pindrop-experiment.json" class="text-link">Full experiment JSON ↗</a></div>
<div class="run-banner"><div><span class="status-pill success">COMPLETED</span>
<strong>{esc(pt["strategy"])}</strong><small>{esc(pt["completed_at"])} · {pt["seconds"] / 60:.1f} min ·
CPU, 2 threads</small></div><span class="tag">Frozen selection {esc(pt["selection_frozen_sha256"][:12])}</span></div>
<p>Frozen policy: <strong>{esc(sel["arm"])}</strong> · {esc(sel["layer"])} layer · spacing {sel["spacing"]} px ·
budget {sel["budget"]:.4%} of the valid footprint · halo {sel["halo"]} · tip extension {sel["tip"]} px.
The dense control uses the identical arm, budget, halo and tip with spacing 1. The third file trains the
same layer on catalogue pixels the supplied labels do not contain.</p>
<div class="table-scroll"><table><caption>Arms and their best eligible policy on the tuning fold.</caption>
<thead><tr><th>Arm</th><th>Objective</th><th>Training</th><th>Emitted</th><th>Robust DTI</th></tr></thead>
<tbody>{arms}</tbody></table></div>
<div class="table-scroll"><table><caption>Nested tranches of the selected policy on the tuning fold.
Credit per added pixel is measured, and break-even is the leading-order 0.2 × DTI of that row.</caption>
<thead><tr><th>Budget</th><th>Emitted (tuning)</th><th>Gap DTI</th><th>Added pixels</th><th>Added TP<sub>w</sub></th>
<th>Added FP<sub>w</sub></th><th>Credit per added pixel</th><th>Break-even</th></tr></thead>
<tbody>{tranche}</tbody></table></div>
<div class="table-scroll"><table><caption>Rotated audit fold (offset {esc(part["origin_px"])} px; train folds
{esc(part["training_folds"])}, tune {part["tuning_fold"]}, audit {part["audit_fold"]}). Nothing in this
table could change the frozen recipe.</caption><thead><tr><th>Arm</th><th>Role</th><th>Policy</th>
<th>Emitted</th><th>Gap</th><th>All</th><th>Known</th><th>Far (≥1 km)</th></tr></thead>
<tbody>{audit}</tbody></table></div>
<div class="table-scroll"><table><caption>Paired block bootstrap of the two pre-registered comparisons on
the audit fold.</caption><thead><tr><th>Comparison</th><th>Δ gap</th><th>CI95</th><th>Δ all</th>
<th>CI95</th></tr></thead><tbody>{boots}</tbody></table></div>
<div class="table-scroll"><table><caption>Every earlier published file re-scored here on the
<em>same</em> pindrop-v4 folds, so the comparison is like-for-like. Still a catalogue surrogate, never
the hidden labels.</caption><thead><tr><th>Reference</th><th>File</th><th>Tune gap</th><th>Tune all</th>
<th>Tune known</th><th>Audit gap</th><th>Audit all</th><th>Audit known</th></tr></thead>
<tbody>{refs}</tbody></table></div>
<figure class="gapfinder-figure"><img src="assets/pindrop-preview.png" alt="The published Pindrop nodes file across the footprint: green marks the emitted single-pixel nodes, amber marks the USGS SGMC traces the gap proxy is built from" loading="lazy"><figcaption><strong>The published nodes file.</strong> Green = the {sel["emitted_pixels"]:,} emitted single-pixel nodes ({sel["emitted_fraction"]:.3%} of the template footprint); amber = the USGS SGMC traces the catalogue-gap proxy is built from. Max-pooled 5&times;, which makes a schedule spaced at {sel["spacing"]} px look almost continuous &mdash; the file itself is isolated pixels, not a filled map. Predictions, not confirmed faults, and no competition score exists for it.</figcaption></figure>
<div class="warning-box"><strong>Rotation, not independence.</strong> {esc(pt["config"]["rotation_disclosure"])}</div>
<div class="two-column"><section class="white-card"><span class="eyebrow">DEPLOYED MODEL</span>
<h2>{esc(dep["model_role"])}</h2><dl class="fact-list">
<dt>Refit support</dt><dd>{_pct(dep["refit_support"])}</dd>
<dt>Holdout support</dt><dd>{_pct(dep["holdout_support"])}</dd>
<dt>Refit accepted</dt><dd>{"yes" if dep["refit_accepted"] else "no — frozen holdout model published"}</dd>
<dt>Model file</dt><dd class="mono wrap-anywhere">{esc(dep["model_file"])}</dd>
<dt>Public score</dt><dd>Unknown · no upload performed</dd></dl></section>
<section class="white-card"><span class="eyebrow">WHAT THIS CANNOT SHOW</span><h2>Bounded claims only.</h2>
<ul>{lims}</ul></section></div></section>'''


def pindrop_summary(pt: dict | None, port: dict | None = None) -> str:
    """One honest paragraph for the executive summary: what changed and what it cannot show."""
    if not pt:
        return ""
    match = [row for row in pt["audit"] if row["role"] == "selected"]
    control = [row for row in pt["audit"] if row["role"] == "ridge-control"]
    measured = ""
    if match and control:
        measured = (f' On the audit fold the dense control at the identical budget scored '
                    f'{_num(control[0]["audit"]["gap"]["dti"], 4)} gap DTI against '
                    f'{_num(match[0]["audit"]["gap"]["dti"], 4)} for the spaced schedule.')
    strip = ""
    if port:
        first = port["items"][0]
        strip = (f' The file to upload first is <strong>{esc(first["title"])}</strong> '
                 f'({first["emitted_pixels"]:,} pixels, {first["checks_passed"]}/{first["checks_total"]} '
                 f'format gates) with the Note <code>{esc(first["note"])}</code>.')
    return f'''<section class="section-block"><div class="section-header"><div>
<div class="eyebrow">EXPERIMENT 004 · WHAT CHANGED</div>
<h2>Stop paying for pixels that cover nothing new.</h2></div>
<a href="experiments.html#pindrop" class="text-link">Open the measured record ↗</a></div>
<p>Session 4 keeps the pixel budget of session 3 and changes where the pixels go. The official metric
credits each truth pixel from its single best prediction inside a 300 m kernel, so a dense trace pays
several times for the same coverage. Pindrop ranks every candidate pixel and then accepts one only when
no accepted node is within the suppression square — spacing the emission at the kernel's own
limit.{measured}{strip}</p>
<div class="warning-box">A local catalogue gain is not a leaderboard result. The rotation is disclosed as a
rotation; the hidden labels remain hidden; no file on this site has been uploaded.</div></section>'''


def results_log(results: dict | None) -> str:
    """The platform-response log: only real records, otherwise an explicit empty state.

    An account-level leaderboard number is never rendered here as if it belonged to a file. A record
    exists only when `scripts/record_submission.py` wrote it with the platform's own submission id.
    """
    records = (results or {}).get("records") or []
    if not records:
        return '''<section class="section-block" id="results"><div class="section-header"><div>
<div class="eyebrow">LEADERBOARD RESULTS</div><h2>No submission response has been recorded yet.</h2></div>
<a href="../evidence/leaderboard-results.json" class="text-link">Empty log file ↗</a></div>
<div class="warning-box"><strong>Why this is empty:</strong> none of the published files has been uploaded,
so no public score exists. Recording one is a single command after the platform answers:
<code>python scripts/record_submission.py --file docs/downloads/&lt;file&gt;.tif --submission-id &lt;id&gt;
--score &lt;score&gt; --status accepted --message "&lt;platform wording&gt;"</code>. The script refuses a
score without a submission id and refuses a file that is not in the published portfolio, so a record
always points at a real artifact.</div></section>'''
    rows = "".join(
        f'<tr><td class="mono">{esc(r["submission_id"])}</td><td>{esc(r.get("status", "—"))}</td>'
        f'<td>{_num(r.get("score"), 4)}</td><td>{esc(r.get("variant", "—"))}</td>'
        f'<td class="mono wrap-anywhere">{esc(r["filename"])}</td>'
        f'<td class="mono">{esc(r["sha256"][:10])}</td><td>{esc(r["recorded_at"])}</td></tr>'
        for r in records)
    summary = (results or {}).get("summary") or {}
    return f'''<section class="section-block" id="results"><div class="section-header"><div>
<div class="eyebrow">LEADERBOARD RESULTS</div><h2>Every recorded platform response.</h2></div>
<a href="../evidence/leaderboard-results.json" class="text-link">Raw log ↗</a></div>
<div class="table-scroll"><table><caption>Recorded by <code>scripts/record_submission.py</code>; each row
keeps the platform's submission id next to the file hash, so no score is ever attributed by memory.</caption>
<thead><tr><th>Submission id</th><th>Status</th><th>Public score</th><th>Variant</th><th>File</th>
<th>SHA-256</th><th>Recorded</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="table-note">Best recorded public score: {_num(summary.get("best_public_score"), 4)} from
{summary.get("scored", 0)} scored record(s). These are platform results for the files named beside them,
not local proxy numbers.</p></section>'''
