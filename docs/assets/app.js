/* Static-site UI; every remote browser request is same-origin and relative. */
(function () {
  "use strict";
  let manifest = null;
  let busy = false;
  let sourceFilter = "all";
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  async function getJSON(path) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`Cannot load ${path}: HTTP ${response.status}`);
    return response.json();
  }
  function announce(message, error = false) {
    $$(".build-status").forEach(el => { el.textContent = message; el.classList.toggle("error", error); });
  }
  function save(bytes, name, type) {
    const blob = new Blob([bytes], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = name; link.hidden = true;
    document.body.append(link); link.click(); link.remove();
    // Some browsers consume the Blob asynchronously; do not revoke immediately.
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  async function payload(path, expectedBytes) {
    if (!/^data\/[a-zA-Z0-9._-]+$/.test(path)) throw new Error("Unsafe payload path");
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`Payload unavailable: HTTP ${response.status}`);
    const buffer = new Uint8Array(await response.arrayBuffer());
    if (buffer.byteLength !== expectedBytes) throw new Error("Payload length mismatch. No file downloaded.");
    return buffer;
  }
  async function generate() {
    if (busy || !manifest) return;
    busy = true;
    const buttons = $$(".build-button");
    buttons.forEach(button => { button.disabled = true; button.classList.add("is-loading"); });
    announce("Fetching the pinned prediction field and submission mask…");
    try {
      const [field, mask] = await Promise.all([
        payload(manifest.field.file, manifest.field.bytes), payload(manifest.mask.file, manifest.mask.bytes)
      ]);
      announce("Checking every pixel, writing the GeoTIFF, then reading it back. This can take a few seconds…");
      const result = await window.RiftlineBuilder.build(manifest, field, mask);
      if (!result.passed) throw new Error("Validation did not pass. Download withheld.");
      const note = `${result.note} | tif ${result.sha256.slice(0, 10)}`;
      const noteBox = $("#submission-note"); if (noteBox) { noteBox.value = note; noteBox.style.height = "auto"; noteBox.style.height = noteBox.scrollHeight + "px"; }
      $$(".filename").forEach(el => { el.textContent = result.filename; });
      const hash = $(".file-details .hash");
      if (hash) { hash.textContent = "Generated TIFF SHA-256 "; const code = document.createElement("code"); code.textContent = result.sha256; hash.append(code); }
      save(result.bytes, result.filename, "image/tiff");
      announce(`Built and verified ${result.filename}. TIFF SHA-256: ${result.sha256}. File sent to Downloads; not submitted to DrivenData.`);
      const details = $(".file-details");
      if (details) {
        let receipt = $("#build-receipt");
        if (!receipt) { receipt = document.createElement("button"); receipt.id = "build-receipt"; receipt.type = "button"; receipt.className = "button secondary"; details.append(receipt); }
        receipt.textContent = "Download this build’s receipt";
        receipt.onclick = () => save(JSON.stringify({ filename: result.filename, note, sha256: result.sha256,
          model_artifact_sha256: manifest.artifact.sha256, field_sha256: manifest.field.decoded_sha256,
          template_sha256: manifest.template_sha256, built_at: result.built_at,
          measurements: result.measurement, competition_status: "not uploaded by this site" }, null, 2),
        result.filename.replace(/\.tif$/, ".receipt.json"), "application/json");
      }
    } catch (error) {
      announce(`Build stopped: ${error.message} No generated file was downloaded. The prevalidated direct TIF is available as an alternative.`, true);
    } finally {
      busy = false;
      buttons.forEach(button => { button.disabled = false; button.classList.remove("is-loading"); });
    }
  }
  async function initializeSubmission() {
    if (!$('.build-button')) return;
    try {
      manifest = await getJSON("data/submission.json");
      if (manifest.schema_version !== 1 || manifest.validation.passed !== true) {
        throw new Error("Candidate manifest needs review");
      }
      if (manifest.artifact.sha256 !== $("#submission").dataset.artifactSha256) {
        throw new Error("Page and artifact versions differ. Reload this page before generating a file.");
      }
      if (!window.crypto?.subtle || !window.DecompressionStream || !window.RiftlineBuilder) {
        throw new Error("This browser cannot build securely; use Direct validated TIF");
      }
      $$(".build-button").forEach(button => { button.disabled = false; button.addEventListener("click", generate); });
      announce(`${manifest.validation.checks.length} format gates passed. Ready to build locally—nothing is uploaded.`);
    } catch (error) { manifest = null; announce(error.message, true); }
  }
  $$(".copy-note").forEach(button => button.addEventListener("click", async () => {
    const note = $("#submission-note");
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(note.value);
      button.setAttribute("aria-label", "Submission note copied");
      announce("Submission note copied. Paste it into the Note field beside your uploaded file.");
    } catch (_) { note.focus(); note.select(); announce("Clipboard unavailable here. The note is selected for copying.", true); }
  }));
  function age(timestamp) {
    const t = Date.parse(timestamp);
    if (!Number.isFinite(t) || t > Date.now() + 60000) return null;
    return Math.max(0, (Date.now() - t) / 3600000);
  }
  function dateLabel(timestamp) {
    if (!timestamp || !Number.isFinite(Date.parse(timestamp))) return "verification time unavailable";
    return new Date(timestamp).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
  }
  async function refreshFeed() {
    const status = $("#feed-status"), button = $("#refresh-feed");
    if (button) button.disabled = true;
    try {
      const feed = await getJSON("data/feed.json");
      if (!Array.isArray(feed.sources) || !feed.sources.length) throw new Error("Source evidence is empty");
      const staleAfter = feed.stale_after_hours || 48;
      const issues = feed.sources.filter(source => age(source.last_verified_at) === null || age(source.last_verified_at) > staleAfter || ["refresh-unavailable", "review-required"].includes(source.status));
      const oldest = Math.max(...feed.sources.map(s => age(s.last_verified_at) ?? Infinity));
      if (status) {
        status.replaceChildren(); const dot = document.createElement("span"); dot.className = "dot"; status.append(dot);
        status.append(document.createTextNode(issues.length ? `${issues.length} source checks need review` : `Sources checked · ${oldest < 1 ? "<1h" : Math.floor(oldest) + "h"} ago`));
        status.classList.toggle("stale", issues.length > 0);
      }
      const board = feed.leaderboard;
      if (board) {
        const leader = board.leader, user = board.tracked_user;
        $$("[data-leader-score]").forEach(el => { el.textContent = Number.isFinite(leader?.score) ? leader.score.toFixed(4) : "Unknown"; });
        $$("[data-user-score]").forEach(el => { el.textContent = Number.isFinite(user?.score) ? user.score.toFixed(4) : "Not observed"; });
        $$("[data-leader-name]").forEach(el => { el.textContent = leader?.participant || "Unknown"; });
        const boardAge = age(board.verified_at);
        $$("[data-board-time]").forEach(el => { el.textContent = dateLabel(board.verified_at) + (boardAge === null || boardAge > staleAfter ? " · STALE" : ""); });
      }
      const summary = $("#feed-summary");
      if (summary) summary.textContent = `${feed.sources.length - issues.length}/${feed.sources.length} source checks current without refresh alerts. Snapshot ${dateLabel(feed.generated_at)}. Source success times may be older.`;
      const alerts = $("#feed-alerts");
      if (alerts) {
        alerts.replaceChildren();
        if (!issues.length) { const p = document.createElement("p"); p.className = "feed-ok"; p.textContent = "All monitored sources have recent evidence and no outstanding refresh errors. This verifies listed claims, not every possible interpretation."; alerts.append(p); }
        issues.forEach(source => {
          const p = document.createElement("p"); p.className = "feed-alert";
          p.textContent = `${source.title}: ${source.status}. Last success: ${dateLabel(source.last_verified_at)}. ${source.error || "Source or claim freshness requires review."}`;
          alerts.append(p);
        });
      }
      $$("[data-source-id]").forEach(el => {
        const source = feed.sources.find(s => s.id === el.dataset.sourceId);
        if (source) {
          const needsReview = issues.includes(source);
          el.textContent = needsReview ? "Review / stale" : source.status;
          el.classList.toggle("unavailable", needsReview);
          const time = el.parentElement.querySelector("small"); if (time) time.textContent = dateLabel(source.last_verified_at);
        }
      });
    } catch (error) {
      if (status) { status.textContent = "Feed unavailable · verify sources"; status.classList.add("stale"); }
      const summary = $("#feed-summary"); if (summary) summary.textContent = `Snapshot unavailable: ${error.message}. Dates printed in the table are historical, not live checks.`;
    } finally { if (button) button.disabled = false; }
  }
  function filterSources() {
    const query = ($("#source-search")?.value || "").toLowerCase(); let count = 0;
    $$("#source-table tbody tr").forEach(row => {
      const keep = (sourceFilter === "all" || row.dataset.sourceKind === sourceFilter) && row.textContent.toLowerCase().includes(query);
      row.hidden = !keep; if (keep) count++;
    });
    const output = $("#source-count"); if (output) output.textContent = `${count} source${count === 1 ? "" : "s"}`;
  }
  $$("[data-canonical-download]").forEach(link => link.addEventListener("click", () => {
    if (!manifest) return;
    const note = $("#submission-note"); if (note) note.value = manifest.note;
    $$(".filename").forEach(el => { el.textContent = manifest.artifact.filename; });
    const hash = $(".file-details .hash");
    if (hash) { hash.textContent = "Canonical TIFF SHA-256 "; const code = document.createElement("code"); code.textContent = manifest.artifact.sha256; hash.append(code); }
    $("#build-receipt")?.remove();
    announce("Downloading the canonical, locally validated artifact. The note now identifies that file, not a prior browser build.");
  }));
  $("#source-search")?.addEventListener("input", filterSources);
  $$(".filter").forEach(button => button.addEventListener("click", () => {
    sourceFilter = button.dataset.filter;
    $$(".filter").forEach(other => { const active = other === button; other.classList.toggle("active", active); other.setAttribute("aria-pressed", String(active)); });
    filterSources();
  }));
  $("#refresh-feed")?.addEventListener("click", refreshFeed);
  initializeSubmission(); refreshFeed();
})();
