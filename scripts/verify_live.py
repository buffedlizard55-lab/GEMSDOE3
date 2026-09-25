#!/usr/bin/env python3
"""Verify actual public HTTP bytes after Pages deployment; never infer deployment from a build."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gems3.common import read_json, utc_now, write_json  # noqa: E402


def fetch(url, limit):
    raw = bytearray()
    with requests.get(url, timeout=(12, 40), stream=True, headers={'Cache-Control': 'no-cache'}) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw) > limit:
                raise ValueError('Published response exceeds its bounded size')
    return bytes(raw)


def verify(base, expected):
    base = base.rstrip('/')
    query = '?verification=' + utc_now().replace(':', '').replace('-', '')
    page = fetch(base + '/docs/index.html' + query, 1000000)
    if b'Build &amp; download' not in page and b'Build & download' not in page:
        raise ValueError('Published page does not contain the expected submission interface')
    manifest = json.loads(fetch(base + '/docs/data/submission.json' + query, 2000000))
    if manifest['artifact']['sha256'] != expected['artifact']['sha256']:
        raise ValueError('Public candidate identity differs from this release')
    checks = []
    for key in ['artifact', 'zip', 'field', 'mask']:
        spec = expected[key]
        raw = fetch(base + '/docs/' + spec['file'] + query, spec['bytes'])
        if len(raw) != spec['bytes'] or hashlib.sha256(raw).hexdigest() != spec['sha256']:
            raise ValueError(f'Public {key} bytes do not match the release')
        checks.append({'kind': key, 'file': spec['file'], 'bytes': len(raw), 'sha256': spec['sha256'], 'passed': True})
    feed = json.loads(fetch(base + '/docs/data/feed.json' + query, 2000000))
    return {'checked_at': utc_now(), 'base_url': base, 'passed': True, 'checks': checks,
            'public_feed_generated_at': feed.get('generated_at'), 'public_feed_alert_count': len(feed.get('alerts', [])),
            'scope': 'HTTP deployment/byte identity only; locality is explicit in base_url; source alerts and unknown competition score remain separate'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-url', default='https://buffedlizard55-lab.github.io/GEMSDOE3')
    ap.add_argument('--report', type=Path, default=ROOT/'evidence/public-deployment.json')
    ap.add_argument('--attempts', type=int, default=1)
    args = ap.parse_args()
    if not 1 <= args.attempts <= 6:
        raise SystemExit('Use 1–6 bounded attempts')
    expected = read_json(ROOT/'docs/data/submission.json')
    for attempt in range(args.attempts):
        try:
            result = verify(args.base_url, expected)
            write_json(args.report, result)
            print(json.dumps(result, indent=2))
            break
        except (requests.RequestException, ValueError, KeyError) as exc:
            write_json(args.report, {'checked_at': utc_now(), 'base_url': args.base_url,
                       'passed': False, 'error': str(exc)[:600], 'attempt': attempt + 1})
            if attempt == args.attempts - 1:
                raise
            time.sleep(min(5 * 2**attempt, 40))
