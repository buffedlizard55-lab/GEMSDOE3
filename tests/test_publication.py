import json
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

from gems3.common import ROOT, read_json
from scripts.check_published import check_published


def test_published_files_and_actual_javascript_writer():
    result = check_published()
    assert result["direct_tif"] and result["zip"]
    assert result["javascript_writer"]["passed"]
    assert result["independent_rasterio_validation"]["passed"]


def test_browser_refuses_corruption_and_independent_mask_mismatch(tmp_path):
    script = r'''
    const fs = require('fs'), zlib = require('zlib'), crypto = require('crypto');
    const b = require('./docs/assets/submission-builder.js');
    const original = JSON.parse(fs.readFileSync('docs/data/submission.json'));
    const field = fs.readFileSync('docs/' + original.field.file);
    const mask = fs.readFileSync('docs/' + original.mask.file);
    (async()=>{
      const corrupt = Buffer.from(field); corrupt[0] ^= 1;
      let failures = 0;
      try { await b.build(original, corrupt, mask); } catch(e) { if (/SHA-256/.test(e.message)) failures++; }
      const meta = structuredClone(original);
      const wrongMask = zlib.inflateSync(mask); wrongMask.fill(0);
      const packed = zlib.deflateSync(wrongMask);
      meta.mask.bytes = packed.length;
      meta.mask.sha256 = crypto.createHash('sha256').update(packed).digest('hex');
      meta.mask.decoded_sha256 = crypto.createHash('sha256').update(wrongMask).digest('hex');
      try { await b.build(meta, field, packed); } catch(e) { if (/mask/.test(e.message)) failures++; }
      if(failures !== 2) throw new Error('Did not reject both corrupt field and incorrect reference mask');
      const a = b.identity(original, new Date('2026-09-25T00:00:00Z'), '11111111');
      const c = b.identity(original, new Date('2026-09-25T00:00:00Z'), '22222222');
      if(a.filename===c.filename || !a.filename.endsWith('.tif')) throw new Error('Bad identity');
      console.log('negative browser checks passed');
    })().catch(e=>{console.error(e);process.exit(1)});
    '''
    run = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert run.returncode == 0, run.stderr


def test_data_inventory_and_no_leaderboard_claim():
    data, report = read_json(ROOT / 'docs/data/data-inventory.json'), read_json(ROOT / 'docs/data/experiment.json')
    assert data["passed"] and len(data["bands"]) == 19
    assert report["competition_score"] is None and report["competition_submission_id"] is None
    assert report["artifact"]["new_pixel_field"]["different_valid_pixels"] > 0
    assert report["selected"]["eligible"] is True
    assert report["selected"]["arm"] == max([c for c in report["candidates"] if c["eligible"]], key=lambda c: c["tuning"]["dti"])["arm"]
    assert report["deployment"]["published_support_fraction"] <= report["config"]["max_emitted_fraction"]


def test_strict_json_everywhere_in_active_evidence():
    def reject(value):
        raise ValueError('Nonstandard JSON number: ' + value)
    for base in ['docs/data', 'evidence', 'research', 'configs']:
        for path in (ROOT / base).glob('*.json'):
            json.loads(path.read_text(), parse_constant=reject)


def test_download_is_prominent_in_home_and_summary():
    for name in ['index.html', 'executive_summary.html']:
        soup = BeautifulSoup((ROOT / 'docs' / name).read_text(), 'html.parser')
        card = soup.select_one('#submission')
        assert card and card.select_one('.build-button')
        assert len(soup.select('#submission-note')) == 1
        link = next(a for a in card.find_all('a') if a.get_text(strip=True) == 'Direct validated TIF')
        assert (ROOT / 'docs' / link['href']).is_file()
        assert 'Not yet competition-scored.' in card.get_text()
        assert soup.select_one('nav a[aria-current="page"]')


def test_local_links_do_not_escape_or_point_to_missing_files():
    from urllib.parse import unquote, urlsplit
    for page in (ROOT / 'docs').glob('*.html'):
        soup = BeautifulSoup(page.read_text(), 'html.parser')
        for tag in soup.find_all(['a', 'link', 'script', 'img']):
            url = tag.get('href') or tag.get('src')
            if not url or url.startswith(('#', 'https:', 'http:', 'mailto:', 'data:')):
                continue
            target = (page.parent / unquote(urlsplit(url).path)).resolve()
            assert ROOT in target.parents and target.exists(), (page.name, url)


def test_rebuilding_html_is_deterministic():
    paths = sorted((ROOT / 'docs').glob('*.html'))
    before = {p.name: p.read_bytes() for p in paths}
    result = subprocess.run([str(Path(__import__('sys').executable)), '-m', 'gems3.site'],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert before == {p.name: p.read_bytes() for p in paths}


def test_publisher_recomputes_support_instead_of_trusting_report(tmp_path):
    import shutil

    import pytest

    from gems3.common import write_json
    from gems3.publish import publish
    report = read_json(ROOT/'docs/data/experiment.json')
    report['deployment']['published_support_fraction'] = 0.99
    name = report['artifact']['filename']
    shutil.copyfile(ROOT/'docs/downloads'/name, tmp_path/name)
    write_json(tmp_path/'experiment.json', report)
    with pytest.raises(ValueError, match='support disagrees'):
        publish(tmp_path/'experiment.json', tmp_path/'public')
    assert not (tmp_path/'public/data/submission.json').exists()
