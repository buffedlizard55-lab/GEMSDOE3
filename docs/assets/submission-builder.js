/* Riftline browser builder. Precomputed model field -> new, independently read-back GeoTIFF.
 * No model training, data upload, credentials or third-party browser requests.
 * The low-level TIFF writer is preserved from the pinned upstream project; see THIRD_PARTY.md.
 */
(function (root) {
  "use strict";
  const writer = typeof module !== "undefined" && module.exports
    ? require("./geotiff-writer.js") : root.GemsGeoTIFF;
  function assert(ok, message) { if (!ok) throw new Error(message); }
  function equalArray(a, b) { return Array.isArray(a) && a.length === b.length && a.every((v, i) => v === b[i]); }
  async function digest(bytes) { return writer.sha256Hex(bytes); }

  async function inflateBounded(bytes, expected) {
    assert(Number.isSafeInteger(expected) && expected > 0 && expected <= 100000000, "Invalid decoded size");
    assert(typeof root.DecompressionStream === "function", "Browser decompression unavailable. Use the prevalidated direct TIF download.");
    const reader = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate")).getReader();
    const chunks = []; let total = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        total += value.byteLength;
        assert(total <= expected, "Decoded payload exceeds its pinned length");
        chunks.push(value);
      }
    } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    assert(total === expected, "Truncated decoded payload");
    const out = new Uint8Array(total); let offset = 0;
    for (const chunk of chunks) { out.set(chunk, offset); offset += chunk.byteLength; }
    return out;
  }
  async function decodeAndCheck(spec, bytes) {
    assert(bytes.byteLength === spec.bytes && bytes.byteLength <= 20000000, "Compressed payload size mismatch");
    assert(await digest(bytes) === spec.sha256, "Compressed payload SHA-256 mismatch");
    const out = await inflateBounded(bytes, spec.decoded_bytes);
    assert(await digest(out) === spec.decoded_sha256, "Decoded payload SHA-256 mismatch");
    return out;
  }
  function validateField(field, mask, meta) {
    const count = meta.grid.width * meta.grid.height;
    assert(field.length === count && mask.length === Math.ceil(count / 8), "Field/mask shape mismatch");
    let valid = 0, outside = 0, nonzero = 0, min = 1, max = 0;
    for (let i = 0; i < count; i++) {
      const inside = (mask[i >> 3] >> (i & 7)) & 1;
      const v = field[i];
      if (inside) {
        assert(Number.isFinite(v) && v >= 0 && v <= 1, "Invalid value inside template mask at pixel " + i);
        valid++; if (v > 0) nonzero++; min = Math.min(min, v); max = Math.max(max, v);
      } else { assert(Number.isNaN(v), "Non-NaN value outside template mask at pixel " + i); outside++; }
    }
    assert(valid > 0 && valid === meta.valid_pixels, "Template valid-pixel count mismatch");
    assert(outside === meta.outside_pixels, "Template outside-pixel count mismatch");
    assert(nonzero > 0 && nonzero === meta.nonzero_pixels, "Empty or changed prediction support");
    return { valid, outside, nonzero, min, max };
  }
  function identity(meta, date, nonce) {
    const builtAt = (date || new Date()).toISOString();
    const stamp = builtAt.replace(/[-:.]/g, "");
    const salt = nonce || root.crypto.randomUUID().slice(0, 8);
    const safeArm = String(meta.arm).replace(/[^a-z0-9-]/gi, "-");
    return { filename: `riftline-${safeArm}-${stamp}-${meta.candidate_id}-${salt}.tif`,
      note: `${meta.note} | build ${stamp} ${salt}`, built_at: builtAt };
  }
  async function build(meta, compressedField, compressedMask, options) {
    assert(meta.schema_version === 1 && meta.validation.passed === true, "Manifest is not format-validated");
    const g = meta.grid, count = g.width * g.height;
    assert(Number.isSafeInteger(g.width) && Number.isSafeInteger(g.height) && g.width > 0 && g.height > 0 && count <= 20000000, "Unsafe grid dimensions");
    assert(g.epsg === 32611 && equalArray(g.res, [100, 100]), "Unexpected competition grid");
    assert(equalArray(g.transform, [100, 0, g.origin[0], 0, -100, g.origin[1]]), "Inconsistent grid transform");
    assert(new Uint8Array(new Uint16Array([1]).buffer)[0] === 1, "Unsupported byte order; use the direct TIF");
    assert(meta.field.decoded_bytes === count * 4 && meta.mask.decoded_bytes === Math.ceil(count / 8), "Manifest pixel-byte count mismatch");
    const [raw, mask] = await Promise.all([decodeAndCheck(meta.field, compressedField), decodeAndCheck(meta.mask, compressedMask)]);
    const field = new Float32Array(raw.buffer, raw.byteOffset, count);
    const measurement = validateField(field, mask, meta);
    const built = await writer.buildGeoTIFF(field, g, options || {});
    const info = writer.parseGeoTIFF(built.bytes);
    assert(info.width === g.width && info.height === g.height && info.samplesPerPixel === 1, "Written TIFF shape/band mismatch");
    assert(info.bitsPerSample === 32 && info.sampleFormat === 3, "Written TIFF is not float32");
    assert(info.epsg === 32611 && info.rasterType === 1 && equalArray(info.geoTransform, g.transform), "Written TIFF georeferencing mismatch");
    assert(info.nodata === "nan", "Written TIFF lacks NaN nodata");
    const reread = await writer.readField(built.bytes, info);
    const rereadBytes = new Uint8Array(reread.buffer, reread.byteOffset, reread.byteLength);
    assert(await digest(rereadBytes) === meta.field.decoded_sha256, "Written TIFF pixels differ on read-back");
    validateField(reread, mask, meta);
    return { bytes: built.bytes, sha256: await digest(built.bytes), measurement, layout: built.layout,
      ...identity(meta), passed: true, meaning: "Locally generated and checked; not uploaded or competition-scored" };
  }
  const api = { build, validateField, identity, inflateBounded, digest };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RiftlineBuilder = api;
})(typeof window !== "undefined" ? window : globalThis);
