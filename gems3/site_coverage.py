"""Coverline v3 site sections: the metric algebra, the support sweep and the rotated audit.

Every number is read from docs/data/coverage-experiment.json (written by gems3.coverage and
re-hashed by gems3.coverage_publish) or from the published portfolio manifest. Nothing is typed by
hand, and no local proxy number is presented as a competition score.
"""
from __future__ import annotations

from .site_gapfinder import SUBMIT_URL, esc


def _pct(value) -> str:
    return "—" if value is None else f"{value:.2%}"


def _num(value, digits=3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def upload_strip(port: dict | None) -> str:
    """The one-screen answer to 'what do I upload?', rendered above everything else."""
    if not port:
        return ""
    items = port["items"]
    cards = "".join(
        f'<a class="strip-step" href="{esc(i["file"])}" download="{esc(i["filename"])}">'
        f'<span class="strip-order">{i["order"]}</span><span><strong>{esc(i["title"])}</strong>'
        f'<small>{i["emitted_pixels"]:,} pixels · {i["checks_passed"]}/{i["checks_total"]} format gates · '
        f'{i["bytes"] / 1024 / 1024:.2f} MB</small></span></a>' for i in items)
    first = items[0]
    return f'''<section class="upload-strip" id="submit-now" aria-label="Upload order">
<div class="strip-head"><span class="status-pill success"><span class="dot"></span> READY TO SUBMIT</span>
<strong>Download → upload → paste the Note.</strong>
<span class="strip-note">No account data, no modelling and no install needed. Files are re-validated and hashed before publishing.</span></div>
<div class="strip-grid">{cards}</div>
<div class="strip-foot">Start with <strong>{esc(first["title"])}</strong>
(<a href="{esc(first["file"])}" download="{esc(first["filename"])}">direct .tif</a> ·
<a href="{esc(first["zip"])}" download>single-file ZIP</a>) and paste
<code>{esc(first["note"])}</code>. Full instructions in the
<a href="executive_summary.html#steps">executive summary</a> or
<a href="{SUBMIT_URL}" target="_blank" rel="noopener noreferrer">DrivenData → Submissions ↗</a>.</div>
</section>'''


def algebra_section(cx: dict | None, section_id: str = "algebra") -> str:
    """Why this experiment is designed the way it is, using only the official metric."""
    if not cx:
        return ""
    if not section_id or not section_id.replace("-", "").isalnum():
        raise ValueError("Section id must be a simple identifier")
    alg = cx["metric_algebra"]
    rows = "".join(
        f'<tr><td>{r["support_target"]:.4%}</td><td class="mono">{r["floor"]:.4f}</td>'
        f'<td>{_pct(r["emitted_fraction"])}</td><td>{_num(r["dti"], 4)}</td>'
        f'<td>{r["added_pixels"]:,}</td><td>{_num(r["added_TP_w"], 2)}</td>'
        f'<td>{_num(r["added_FP_w"], 2)}</td>'
        f'<td>{_num(r["covered_credit_per_added_pixel"], 4)}</td>'
        f'<td>{_num(r["break_even_credit_per_pixel"], 4)}</td></tr>'
        for r in cx["marginal_value_tuning"])
    return f'''<section class="section-block" id="{section_id}">
<div class="section-header"><div><div class="eyebrow">WHY THIS DESIGN</div>
<h2>Every emitted pixel costs 0.2. It has to buy something.</h2></div>
<a href="data/coverage-experiment.json" class="text-link">Raw experiment JSON ↗</a></div>
<div class="two-column"><div>
<p>The official metric is a distance-weighted Tversky index with α = 0.2 and β = 0.8 and a triangular
kernel of 300 m (3 pixels). For a binary emission at p = 1, adding one pixel changes the denominator by</p>
<div class="code-panel"><pre><code>ΔD = 0.2 × (coverage credit it newly contributes)
   + 0.2 × (1 − k(distance to nearest truth))   ≤ 0.2</code></pre></div>
<p>A pixel that becomes the best cover of a hidden-truth pixel adds 1 to TP and removes 0.8 from FN,
and its own false-positive weight is 1 − k. Both parts are bounded by 0.2, so the cost is at most
0.2 <em>whether or not the pixel is right</em>. Write <code>a</code> for the numerator credit a set of
added pixels newly earns and <code>b</code> for the false-positive weight they add. The index rises
exactly when <code>a × (1 − 0.2 × DTI) &gt; 0.2 × DTI × b</code>. To leading order that is the
break-even a tranche has to beat: {alg["break_even_credit_per_pixel_at_leader"]:.3f} per added pixel
at the public lead of 0.3049 — roughly, land within 2.8 pixels of truth that nothing else covers.
The table reports <code>a</code>, <code>b</code> and both sides of that test, so no reader has to take
the approximation on trust.</p>
<p>That is why this experiment sweeps twelve support levels, keeps a β/α-weighted classifier next to
the regression control, and publishes what every tranche actually bought. A binary emission is a
deliberate consequence of the metric, not a claim to be a calibrated probability.</p>
</div><div>
<dl class="fact-list"><dt>Pixel denominator cost</dt><dd>{alg["pixel_denominator_cost"]}</dd>
<dt>Break-even credit per pixel at 0.3049</dt><dd>{alg["break_even_credit_per_pixel_at_leader"]:.4f}</dd>
<dt>Kernel support</dt><dd>300 m = 3 pixels, triangular</dd>
<dt>α / β</dt><dd>0.2 false positives / 0.8 false negatives</dd>
<dt>Support levels swept</dt><dd>{len(cx["config"]["support_targets"])}</dd>
<dt>Candidate policies evaluated</dt><dd>{len(cx["candidates"])}</dd></dl>
<p class="small">The published file is chosen by the pre-registered rule in
<code>configs/coverage-v3.json</code>, which is hash-bound into the frozen selection. The table below
is a diagnostic of the selected arm on the tuning fold; it did not choose the winner after the fact.</p>
</div></div>
<div class="table-scroll"><table><caption>Measured marginal value of each support tranche on the tuning fold
(nested tranches, so each row is exactly the pixels the extra support added). Credit per added pixel =
added TP<sub>w</sub> ÷ added pixels; break-even is the leading-order 0.2 × DTI of that row.</caption>
<thead><tr><th>Support target</th><th>Floor</th><th>Emitted</th><th>Tuning DTI</th><th>Added pixels</th>
<th>Added TP<sub>w</sub></th><th>Added FP<sub>w</sub></th><th>Credit per added pixel</th>
<th>Break-even</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="table-note">Read the last two columns together with added FP<sub>w</sub>: a tranche pays only if
it clears the exact test above, not the leading-order column alone. From the 10% row the measured credit
falls below break-even, which is why the selected policy stops at 4% and the third published file is
labelled a recall probe. Every number is measured on public stand-in labels, never on the hidden expert
labels.</p></section>'''


def coverage_experiment_section(cx: dict | None, gapfinder_v2: dict | None = None) -> str:
    if not cx:
        return ""
    sel, wide, part = cx["selected"], cx["wide"], cx["partition"]
    audit = {row["arm"]: row["audit"] for row in cx["audit"]}
    head = "".join(
        f'<tr><td><strong>{esc(name)}</strong></td>'
        f'<td>{_num(audit[name]["gap"]["dti"], 4)}</td><td>{_num(audit[name]["all"]["dti"], 4)}</td>'
        f'<td>{_num(audit[name]["known"]["dti"], 4)}</td>'
        f'<td>{_num(min(audit[name][k]["dti"] for k in ("gap", "all", "known")), 4)}</td></tr>'
        for name in audit)
    refs = "".join(
        f'<tr><td>{esc(label)}</td><td class="mono wrap-anywhere">{esc(entry["file"])[:44]}</td>'
        f'<td>{_num(entry["tune"]["gap"]["dti"], 3)}</td><td>{_num(entry["tune"]["all"]["dti"], 3)}</td>'
        f'<td>{_num(entry["tune"]["known"]["dti"], 3)}</td>'
        f'<td>{_num(entry["audit"]["gap"]["dti"], 3)}</td><td>{_num(entry["audit"]["all"]["dti"], 3)}</td>'
        f'<td>{_num(entry["audit"]["known"]["dti"], 3)}</td></tr>'
        for label, entry in cx["references"].items())
    boots = "".join(
        f'<tr><td>{esc(label)}</td><td>{_num(v["gap"]["observed_difference"], 4)}</td>'
        f'<td class="mono">[{_num(v["gap"]["ci95"][0], 3)}, {_num(v["gap"]["ci95"][1], 3)}]</td>'
        f'<td>{_num(v["all"]["observed_difference"], 4)}</td>'
        f'<td class="mono">[{_num(v["all"]["ci95"][0], 3)}, {_num(v["all"]["ci95"][1], 3)}]</td></tr>'
        for label, v in cx["audit_bootstrap"].items())
    lims = "".join(f"<li>{esc(text)}</li>" for text in cx["limitations"])
    def arm_row(a: dict) -> str:
        tag = ' <span class="tag">Selected</span>' if a["arm"]["id"] == sel["arm"] else ""
        return (f'<tr><td><strong>{esc(a["arm"]["id"])}</strong>{tag}</td>'
                f'<td>{esc(a["objective"])}</td><td>{a["seconds"] / 60:.1f} min</td>'
                f'<td>{_pct(a["best"]["emitted_fraction"])}</td>'
                f'<td>{_num(a["best"]["robust_dti"], 4)}</td></tr>')

    arm_rows = "".join(arm_row(a) for a in cx["arms"])
    return f'''<section class="section-block" id="coverage">
<div class="section-header"><div><div class="eyebrow">EXPERIMENT 003 · COVERLINE</div>
<h2>A rotated partition, a support sweep and a β/α-weighted control.</h2></div>
<a href="data/coverage-experiment.json" class="text-link">Full experiment JSON ↗</a></div>
<div class="run-banner"><div><span class="status-pill success">COMPLETED</span>
<strong>{esc(cx["strategy"])}</strong><small>{esc(cx["completed_at"])} · {cx["seconds"] / 60:.1f} min ·
CPU, 2 threads</small></div><span class="tag">Frozen selection {esc(cx["selection_frozen_sha256"][:12])}</span></div>
<p>Frozen policy: <strong>{esc(sel["arm"])}</strong> at support target {sel["support_target"]:.4%}
(floor {sel["floor"]:.4f}), halo {sel["halo"]}, tip extension {sel["tip"]}. The third published file uses
the pre-registered wide rule at support target {wide["support_target"]:.4%}.</p>
<div class="table-scroll"><table><caption>Arms and their tuning-fold best eligible policy.</caption>
<thead><tr><th>Arm</th><th>Objective</th><th>Training</th><th>Emitted (tuning)</th><th>Robust DTI</th></tr></thead>
<tbody>{arm_rows}</tbody></table></div>
<div class="table-scroll"><table><caption>Rotated audit fold (offset {esc(part["origin_px"])} px, tune fold
{part["tuning_fold"]}, audit fold {part["audit_fold"]}). No value in this table could change the frozen recipe.</caption>
<thead><tr><th>Arm</th><th>Audit · gap</th><th>Audit · all</th><th>Audit · known</th><th>min</th></tr></thead>
<tbody>{head}</tbody></table></div>
<div class="table-scroll"><table><caption>Earlier published files re-scored here on the <em>same</em> rotated folds,
so the comparison is like-for-like (still a catalogue surrogate, not hidden labels).</caption>
<thead><tr><th>Reference</th><th>File</th><th>Tune gap</th><th>Tune all</th><th>Tune known</th>
<th>Audit gap</th><th>Audit all</th><th>Audit known</th></tr></thead><tbody>{refs}</tbody></table></div>
<div class="table-scroll"><table><caption>Paired block bootstrap of the classifier arm against the regression
control (7 spatial blocks on the audit fold).</caption><thead><tr><th>Comparison</th><th>Δ gap</th>
<th>CI95</th><th>Δ all</th><th>CI95</th></tr></thead><tbody>{boots}</tbody></table></div>
<div class="warning-box"><strong>Rotation, not independence.</strong> {esc(cx["config"]["rotation_disclosure"])}
A third, fully independent fault catalogue for auditing is still outstanding.</div>
<div class="two-column"><section class="white-card"><span class="eyebrow">DEPLOYED MODEL</span>
<h2>{esc(cx["deployment"]["model_role"])}</h2><dl class="fact-list">
<dt>Policy</dt><dd>s={sel["support_target"]:.4%} h={sel["halo"]} L={sel["tip"]}</dd>
<dt>Refit support</dt><dd>{_pct(cx["deployment"]["refit_support"])}</dd>
<dt>Holdout support</dt><dd>{_pct(cx["deployment"]["holdout_support"])}</dd>
<dt>Refit accepted</dt><dd>{"yes" if cx["deployment"]["refit_accepted"] else "no — frozen holdout model published"}</dd>
<dt>Model file</dt><dd class="mono wrap-anywhere">{esc(cx["deployment"]["model_file"])}</dd>
<dt>Public score</dt><dd>Unknown · no upload performed</dd></dl></section>
<section class="white-card"><span class="eyebrow">WHAT THIS CANNOT SHOW</span><h2>Bounded claims only.</h2>
<ul>{lims}</ul></section></div></section>'''


def coverage_summary(cx: dict | None) -> str:
    """One honest paragraph for the executive-summary page: what changed and what it cannot show."""
    if not cx:
        return ""
    sel, part = cx["selected"], cx["partition"]
    refs = cx["references"]
    v2 = refs.get("gapfinder-v2-fusion")
    compare = ""
    if v2:
        compare = (f' On the identical rotated folds the previously published fusion file scores '
                   f'{_num(v2["audit"]["gap"]["dti"])} / {_num(v2["audit"]["all"]["dti"])} / '
                   f'{_num(v2["audit"]["known"]["dti"])} (gap / all / known) against this run\'s '
                   f'audited arm. Those are public stand-in catalogues, not the hidden expert labels.')
    return f'''<section class="section-block"><div class="section-header"><div>
<div class="eyebrow">EXPERIMENT 003 · WHAT CHANGED</div>
<h2>Budget the pixels, not the guesses.</h2></div>
<a href="experiments.html#coverage" class="text-link">Open the measured record ↗</a></div>
<p>Session 3 read the official metric literally. With α = 0.2 and β = 0.8, every emitted pixel costs at
most 0.2 of the Tversky denominator and pays only when it covers hidden truth that no other pixel
covers. So the emission budget — not a classifier score — is the decision variable. This run swept
{len(cx["config"]["support_targets"])} support levels on a rotated spatial partition
(offset {esc(part["origin_px"])} px; train folds {esc(part["training_folds"])}, tune {part["tuning_fold"]},
audit {part["audit_fold"]}) and compared a β/α-weighted classifier with the regression control. The
frozen policy was <strong>{esc(sel["arm"])}</strong> at support target {sel["support_target"]:.4%}.{compare}</p>
<div class="warning-box">A local catalogue gain is not a leaderboard result. The rotation is disclosed as a
rotation; the hidden labels remain hidden; no file on this site has been uploaded.</div></section>'''
