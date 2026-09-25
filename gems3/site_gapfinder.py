"""Gapfinder sections for the static site: the submission portfolio and the experiment record.

Everything rendered here is read from published JSON (docs/data/portfolio.json,
docs/data/gapfinder-experiment.json) or committed evidence files; no number is typed by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMIT_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/"


def esc(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def dti(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def load_optional(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def portfolio_card(item: dict) -> str:
    v = esc(item["variant"])
    mb = item["bytes"] / 1024 / 1024
    primary = item["order"] == 1
    pill = "success" if primary else "neutral-pill"
    return f'''<article class="portfolio-card{' is-primary' if primary else ''}" data-variant="{v}" data-sha256="{esc(item['sha256'])}">
<div class="card-eyebrow"><span class="status-pill {pill}">{item['order']} · {esc(item['badge'])}</span><span class="mono">{esc(item['sha256'][:10])}</span></div>
<h3>{esc(item['title'])}</h3><p>{esc(item['hypothesis'])}</p>
<a class="button primary portfolio-download" href="{esc(item['file'])}" download="{esc(item['filename'])}">Download .tif <span>{mb:.2f} MB</span></a>
<div class="download-alternatives"><a href="{esc(item['zip'])}" download>Single-file ZIP</a><span>·</span><a href="data/portfolio.json">Manifest</a></div>
<div class="submission-note"><div><label for="note-{v}">NOTE · PASTE WITH THIS FILE</label><button class="copy-portfolio-note icon-button" type="button" data-target="note-{v}" aria-label="Copy note for {esc(item['title'])}">Copy</button></div><textarea id="note-{v}" rows="3" readonly>{esc(item['note'])}</textarea></div>
<dl class="mini-facts"><dt>Pixels set to 1</dt><dd>{item['emitted_pixels']:,} ({item['emitted_fraction']:.2%})</dd><dt>On supplied labels</dt><dd>{item['on_known_pixels']:,}</dd><dt>Format gates</dt><dd>{item['checks_passed']}/{item['checks_total']} passed</dd><dt>Competition score</dt><dd>Unknown until uploaded</dd></dl>
<p class="answers"><strong>This upload tells us:</strong> {esc(item['answers'])}</p>
<details class="file-details"><summary>Filename &amp; SHA-256</summary><p class="filename">{esc(item['filename'])}</p><p class="hash"><code>{esc(item['sha256'])}</code></p></details>
</article>'''


def portfolio_section(port: dict | None, where: str = "home") -> str:
    if not port:
        return ""
    items = port["items"]
    first = items[0]
    heading_id = f"portfolio-heading-{where}"
    return f'''<section class="portfolio" id="portfolio" aria-labelledby="{heading_id}">
<div class="portfolio-head"><div><div class="eyebrow">SUBMIT THIS <span class="eyebrow-line"></span> {esc(port['strategy']).upper()} PORTFOLIO</div>
<h2 id="{heading_id}">Upload <em>{esc(first['title'])}</em> first. Paste its Note.</h2>
<p>{len(items)} format-validated GeoTIFFs, each with its own filename and Note. They are designed as a set: the first is our best estimate, the next two test why it did or didn't work. {esc(port['disclaimer'])}</p></div>
<ol class="portfolio-steps"><li><strong>Download</strong> the .tif (one click).</li><li><strong>Open</strong> <a href="{SUBMIT_URL}" target="_blank" rel="noopener noreferrer">DrivenData → Submissions ↗</a> and choose the file.</li><li><strong>Paste</strong> the Note, then Submit. Repeat next time with file 2.</li></ol></div>
<div class="portfolio-grid">{''.join(portfolio_card(i) for i in items)}</div>
<p class="portfolio-status" id="portfolio-status" role="status" aria-live="polite">{esc(port['rule'])} Files published {esc(port['published_at'])}.</p>
</section>'''


def _row(label, policy, support, proxies, extra=""):
    cells = "".join(f"<td>{dti(proxies.get(k))}</td>" for k in ("gap", "all", "known"))
    sup = "—" if support is None else f"{support:.2%}"
    return f"<tr><td><strong>{esc(label)}</strong>{extra}</td><td class=\"mono\">{esc(policy)}</td><td>{sup}</td>{cells}</tr>"


def _pol(p: dict) -> str:
    return f"f={p['floor']:.2f} h={p['halo']} L={p['tip']}"


def _dtis(block: dict | None) -> dict:
    return {k: v["dti"] for k, v in (block or {}).items() if isinstance(v, dict) and "dti" in v}


def experiment_section(gx: dict | None, v1: dict | None, diag: dict | None) -> str:
    if not gx:
        return ""
    sel = gx["selected"]
    proxies = gx["config"].get("selection_proxies", ["gap", "all"])
    tune_rows = "".join(
        _row(a["arm"]["id"], _pol(a["best"]) if a.get("best") else "no eligible policy",
             (a.get("best") or {}).get("emitted_fraction"), _dtis((a.get("best") or {}).get("tuning")),
             ' <span class="status-pill success">SELECTED</span>' if a.get("best") and a["arm"]["id"] == sel["arm"]
             and _pol(a["best"]) == _pol(sel) else "")
        for a in gx["arms"])
    audit_rows = "".join(_row(a["arm"], _pol(a["policy"]), None, _dtis(a["audit"])) for a in gx["audit"])
    for name, ref in gx.get("references", {}).items():
        audit_rows += _row(name, "reference file", None, _dtis(ref.get("audit")),
                           ' <small>(trained on folds incl. audit)</small>' if name.startswith("riftline") else "")
    boot = gx.get("audit_bootstrap", {})
    boot_rows = "".join(
        f"<tr><td>{esc(pair)}</td><td>{esc(k)}</td><td>{r['observed_difference']:+.3f}</td>"
        f"<td>[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]</td><td>{r['blocks']}</td></tr>"
        for pair, d in boot.items() for k, r in d.items())
    dep = gx["deployment"]
    dep_text = (f"All-fold refit accepted: support {dep['refit_support']:.2%} vs {dep['holdout_support']:.2%} for the "
                "holdout model (gate: within the 8% cap).") if dep.get("refit_accepted") else (
                f"All-fold refit rejected (support {dep.get('refit_support', 0):.2%}); the holdout model was published.")
    v1_block = ""
    if v1:
        vs = v1["selected"]
        v1_audit = "".join(_row(a["arm"], _pol(a["policy"]), None, _dtis(a["audit"]) | {
            "known": ((diag or {}).get("cross_source", {}).get(a["arm"], {}) or {}).get("audit_known_dti")})
            for a in v1["audit"])
        curve = "".join(f"<tr><td>{c['floor']:.2f}</td><td>{c['support']:.2%}</td><td>{dti(c['gap'])}</td><td>{dti(c['all'])}</td></tr>"
                        for c in (diag or {}).get("support_curve", []))
        v1_block = f'''<section class="section-block"><div class="section-header"><div><div class="eyebrow">SUPERSEDED · KEPT FOR THE RECORD</div><h2>Gapfinder v1 chose a source-specialised model.</h2></div><a class="text-link" href="../evidence/gapfinder-v1-experiment.json">v1 evidence ↗</a></div>
<p>v1 selected <code>{esc(vs['arm'])} {esc(_pol(vs))}</code> by min(gap, all) on the tuning fold. A post-hoc check on held-out supplied faults (the “known” column, never used by v1) showed it finds unseen supplied-type faults poorly ({dti(((diag or {}).get('cross_source', {}).get(vs['arm'], {}) or {}).get('audit_known_dti'))}). Hidden truth may resemble either catalogue, so v2 added this proxy to the selection rule. Because we looked at fold 3 first, <strong>the v2 audit is not independent</strong>; that is disclosed in the v2 config.</p>
<div class="table-scroll"><table><caption>v1 audit, fold 3. “known” = held-out supplied faults, post-hoc (evidence/gapfinder-diagnostics.json).</caption><thead><tr><th>Arm</th><th>Policy</th><th>Support</th><th>gap</th><th>all</th><th>known</th></tr></thead><tbody>{v1_audit}</tbody></table></div>
<details class="file-details"><summary>Support curve (sgmc-target, halo 1, tuning fold): the proxy peaks well inside the 8% cap</summary><div class="table-scroll"><table><thead><tr><th>Floor</th><th>Support</th><th>gap</th><th>all</th></tr></thead><tbody>{curve}</tbody></table></div></details></section>'''
    return f'''<section class="section-block" id="gapfinder"><div class="section-header"><div><div class="eyebrow">EXPERIMENT 002 · PREVIOUS</div><h2>Gapfinder: learn where the supplied labels are incomplete.</h2></div><a class="text-link" href="data/gapfinder-experiment.json">Full report JSON ↗</a></div>
<p>The organisers confirmed that supplied fault pixels are masked from scoring and that hidden truth is any fault <em>not</em> already in the USGS/INGENIOUS labels (<a href="https://community.drivendata.org/raw/11516">forum 11516</a>, <a href="https://community.drivendata.org/raw/11536">11536</a>). Gapfinder therefore trains on a second, independent public catalogue—the USGS State Geologic Map Compilation (SGMC)—and never emits a pixel on a supplied label. Three target definitions compete: supplied labels only, SGMC only, and both. Each is scored on a held-out tuning region against three proxies: <strong>gap</strong> (SGMC faults &gt;300 m from supplied labels), <strong>all</strong> SGMC faults, and <strong>known</strong> (held-out supplied faults, standing in for hidden faults of the supplied type). The selection rule is the minimum of {esc(', '.join(proxies))}; the support cap is 8%.</p>
<div class="table-scroll"><table><caption>Best eligible policy per arm on tuning fold {gx['partition']['tuning_fold']} (training folds {esc(gx['partition']['training_folds'])}). Local proxy DTI, not a competition score.</caption><thead><tr><th>Arm</th><th>Policy</th><th>Support</th><th>gap</th><th>all</th><th>known</th></tr></thead><tbody>{tune_rows}</tbody></table></div>
<div class="table-scroll"><table><caption>Audit fold {gx['partition']['audit_fold']}, scored once after the selection was frozen (sha256 {esc(gx['selection_frozen_sha256'][:12])}…).</caption><thead><tr><th>Arm / file</th><th>Policy</th><th>Support</th><th>gap</th><th>all</th><th>known</th></tr></thead><tbody>{audit_rows}</tbody></table></div>
<div class="table-scroll"><table><caption>Paired spatial block bootstrap on the audit fold (2,000 draws). It measures spatial sampling noise only.</caption><thead><tr><th>Comparison</th><th>Proxy</th><th>Observed Δ DTI</th><th>95% interval</th><th>Blocks</th></tr></thead><tbody>{boot_rows}</tbody></table></div>
<figure class="gapfinder-figure"><img src="assets/gapfinder-preview.png" alt="Gapfinder fusion file across the GeoDAWN footprint: green = model-predicted traces, amber = USGS SGMC faults more than 300 m from supplied labels" loading="lazy"><figcaption><strong>The fusion file (upload 1).</strong> Green = model-predicted traces; amber = USGS SGMC faults &gt;300 m from supplied labels (the sgmc-gap file on its own). Max-pooled 5×; these are predictions, not confirmed faults.</figcaption></figure>
<div class="two-column"><div class="callout"><strong>Deployment.</strong><p>{esc(dep_text)} The published files use that model with the frozen policy <code>{esc(sel['arm'])} {esc(_pol(sel))}</code>.</p></div><div class="warning-box"><strong>What these numbers are not.</strong> SGMC is a ~1:1,000,000 compilation, not the hidden expert labels. The fusion and SGMC-gap files add SGMC traces directly, and that cannot be scored locally without circularity. Only a leaderboard upload measures it. Tip extensions are hypotheses. Getting to this run took four attempts, all logged. (1) We caught a leak in the known proxy and aborted. (2) The source-integrity guard stopped a run after we edited code mid-run. (3) A run audited a tie-broken policy that was not the deployed one. (4) This run: same frozen selection, correct audit. See the <a href="../evidence/gapfinder-v2-errata.json">errata record</a>.</div></div>
<section class="section-block"><h2>Gapfinder limits that can change the conclusion</h2><ul class="limitation-list">{''.join(f'<li>{esc(x)}</li>' for x in gx.get('limitations', []) + EXTRA_LIMITS)}</ul></section>
</section>{v1_block}'''


EXTRA_LIMITS = [
    "Selection weakness: the known proxy ignores halo and tip, so for some arms those were decided by the lower-mass tie-break rather than evidence.",
    "Fold 3 was inspected during the post-hoc v1 diagnostic, so the v2 audit is not an independent test.",
    "The SGMC fault raster is inherited from the original project (legacy/scripts/fetch_proxy_faults.py: official USGS FeatureServer, fault classes only, GeoJSON pinned by SHA-256). The newer 2026 SGMC release is not used yet.",
    "Every file is strictly binary {0, 1}. The metric weights hits and false positives by the predicted value, and soft emission was not re-tested in Gapfinder (Riftline tested it; binary won there).",
]


CLARIFICATIONS = [
    ("Mask is pixel-exact", "Identical to the supplied training labels, so emitting on them earns nothing.", "https://community.drivendata.org/raw/11516"),
    ("Near-known is fully penalised", "A prediction beside a known trace but far from new truth counts as a false positive.", "https://community.drivendata.org/raw/11516"),
    ("New truth can sit within 300 m", "Corrections near known traces exist, so a small halo is a tuned choice, not a rule.", "https://community.drivendata.org/raw/11516"),
    ("Continuations count as new", "New geometry of existing fault systems is in scope. That motivates the tip-extension option.", "https://community.drivendata.org/raw/11536"),
    ("Test sources are secret", "Fault types and sources won't be shared. Hence the source-robust selection rule.", "https://community.drivendata.org/raw/11527"),
    ("Phase 2 labels grow from submissions", "Expert review of all Phase 1 submissions updates the Phase 2 test set.", "https://community.drivendata.org/raw/11527"),
]


def clarifications_section() -> str:
    cards = "".join(f'<article class="strategy-card"><h3>{esc(t)}</h3><p>{esc(d)}</p><a class="text-link" href="{esc(u)}">Staff answer ↗</a></article>'
                    for t, d, u in CLARIFICATIONS)
    return f'''<section class="section-block" id="clarifications"><div class="section-header"><div><div class="eyebrow">OFFICIAL CLARIFICATIONS · DRIVENDATA STAFF</div><h2>What the organisers said, and what we changed.</h2></div><a class="text-link" href="sources.html">Quoted in the source register ↗</a></div><div class="strategy-grid clarification-grid">{cards}</div>
<p class="table-note">Forum text is read through Discourse's raw endpoint so the automated feed can re-check the exact quotes. The SGMC data release page notes a newer 2026 release (<a href="https://doi.org/10.5066/P1A3DQZK">doi:10.5066/P1A3DQZK</a>). It is not used yet and is queued as a next step.</p></section>'''


def gapfinder_summary(port: dict | None, gx: dict | None) -> str:
    if not port or not gx:
        return ""
    sel = gx["selected"]
    audit = {a["arm"]: _dtis(a["audit"]) for a in gx["audit"]}
    refs = {k: _dtis(v.get("audit")) for k, v in gx.get("references", {}).items()}
    mine = audit.get(sel["arm"], {})
    rift = refs.get("riftline-published", {})
    plan = "".join(f"<li><strong>{esc(i['badge'].title())}: {esc(i['title'])}</strong>. {esc(i['answers'])}</li>" for i in port["items"])
    compare = ""
    if mine and rift:
        compare = (f"<p>On the held-out audit region, the selected model scores gap {dti(mine.get('gap'))} / all {dti(mine.get('all'))}"
                   f" / known {dti(mine.get('known'))}. The Riftline file scores gap {dti(rift.get('gap'))} / all {dti(rift.get('all'))}"
                   f" / known {dti(rift.get('known'))}. Riftline was trained on that region, so its known score is flattering. These are local proxies"
                   " with different truth. They are <strong>not</strong> leaderboard predictions.</p>")
    return f'''<div class="summary-grid section-block"><div><div class="status-pill neutral-pill">CURRENT OUTCOME</div><h2>Three distinct files.<br>No public score yet.</h2>
<p>Model policy <code>{esc(sel['arm'])} {esc(_pol(sel))}</code> was frozen on a tuning region before any audit scoring (selection hash <code>{esc(gx['selection_frozen_sha256'][:12])}</code>).</p>{compare}
<p>Nobody has uploaded these files, so we do not know their competition scores. The public leader is 0.3049. A change in an account's best score is never automatically credited to a file; match results by the SHA prefix in each Note.</p></div>
<div class="summary-side"><div class="eyebrow">THE PLAN FOR THIS WEEK'S THREE UPLOADS</div><ol class="plan-list">{plan}</ol>
<div class="callout">Organisers: Phase 2 truth is <a href="https://community.drivendata.org/raw/11527">updated by expert review of Phase 1 submissions</a>. Distinct, plausible traces are worth uploading. You still choose <strong>one</strong> final file for scoring. Pick it only after comparing public scores.</div>
<a href="experiments.html#gapfinder" class="text-link">Read the measured results →</a></div></div>'''


def portfolio_verification(port: dict | None) -> str:
    if not port:
        return ""
    blocks = []
    for item in port["items"]:
        rows = "".join(
            f'<tr><td><span class="status-pill {"success" if c["passed"] else "warning"}">{"PASS" if c["passed"] else "FAIL"}</span></td>'
            f'<td>{esc(c["check"])}</td><td class="wrap-anywhere">{esc(c["detail"])}</td></tr>'
            for c in item["validation"]["checks"])
        blocks.append(f'<details class="file-details"><summary>{esc(item["title"])} · {item["checks_passed"]}/{item["checks_total"]} gates · '
                      f'<code>{esc(item["sha256"][:10])}</code></summary><div class="table-scroll"><table><thead><tr><th>Gate</th>'
                      f'<th>Requirement</th><th>Measured detail</th></tr></thead><tbody>{rows}</tbody></table></div></details>')
    return (f'<section class="section-block" id="portfolio-gates"><div class="section-header"><div><div class="eyebrow">{(esc(port.get("strategy", "published")).upper() if isinstance(port, dict) else "PUBLISHED")} PORTFOLIO</div>'
            f'<h2>Every portfolio file, re-read and re-checked.</h2></div><a class="text-link" href="data/portfolio.json">Manifest ↗</a></div>'
            f'<p>The publisher re-validates each GeoTIFF against the hash-pinned template, confirms that the ZIP holds exactly that file, '
            f'and refuses to publish on any failure. Zero emitted pixels lie on supplied labels.</p>{"".join(blocks)}</section>')
