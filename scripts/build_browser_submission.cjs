#!/usr/bin/env node
/* Headless execution of the exact browser builder; Python independently validates its output. */
const fs = require('node:fs');
const path = require('node:path');
const builder = require('../docs/assets/submission-builder.js');
(async () => {
  const manifestPath = process.argv[2] || 'docs/data/submission.json';
  const output = process.argv[3];
  if (!output) throw new Error('Usage: node scripts/build_browser_submission.cjs MANIFEST OUTPUT.tif');
  const meta = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const base = path.dirname(path.dirname(path.resolve(manifestPath)));
  const result = await builder.build(meta, fs.readFileSync(path.join(base, meta.field.file)), fs.readFileSync(path.join(base, meta.mask.file)));
  if (!result.passed) throw new Error('Builder gate failed');
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, result.bytes);
  console.log(JSON.stringify({ passed: result.passed, sha256: result.sha256, bytes: result.bytes.length,
    measurement: result.measurement, layout: result.layout, note: result.note, filename: result.filename }, null, 2));
})().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
