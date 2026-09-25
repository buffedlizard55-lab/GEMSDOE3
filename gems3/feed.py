"""Refresh fixed official/primary sources. Failed checks never advance last-verified time.

No inference of new facts or invented scores: quotes are matched conservatively, leaderboard
rows are parsed structurally, unknown HTML is an error. Remote text is data, never instructions.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .common import ROOT, read_json, utc_now, write_json

MAX_SOURCE_BYTES = 16 * 1024 * 1024
STALE_HOURS = 48


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", text).casefold())


def age_hours(timestamp: str | None, now: str | None = None) -> float | None:
    if not timestamp:
        return None
    try:
        end = datetime.fromisoformat((now or utc_now()).replace("Z", "+00:00"))
        start = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            return None
        hours = (end - start).total_seconds() / 3600
        return hours if hours >= 0 else None
    except (TypeError, ValueError):
        return None


def source_text(content: bytes, is_pdf: bool) -> str:
    if is_pdf:
        if not content.startswith(b"%PDF"):
            raise ValueError("Expected PDF bytes, received another document")
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    soup = BeautifulSoup(content, "html.parser")
    for item in soup(["script", "style", "noscript"]):
        item.decompose()
    return soup.get_text(" ", strip=True)


def parse_leaderboard(content: bytes | str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    board = next((t for t in soup.find_all("table")
                  if "tversky" in t.get_text(" ", strip=True).casefold()), None)
    if board is None:
        raise ValueError("Leaderboard table or metric header missing; refusing to invent scores")
    rows = []
    for tr in board.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        rank_match = re.fullmatch(r"#?\s*(\d+)", cells[0].get_text(" ", strip=True))
        if not rank_match:
            continue
        score_cells = [(i, c) for i, c in enumerate(cells)
                       if re.fullmatch(r"(?:0(?:\.\d+)?|1(?:\.0+)?)", c.get_text(" ", strip=True)) and i > 1]
        if len(score_cells) != 1:
            raise ValueError("Ambiguous leaderboard score column")
        score_index, score_cell = score_cells[0]
        # The participant cell directly precedes score; team-member avatars are a separate cell.
        participant = cells[score_index - 1]
        user = participant.find("a", href=re.compile(r"/users/"))
        if user and user.get_text(strip=True):
            name = user.get_text(" ", strip=True)
        else:
            name = next((s.strip() for s in participant.stripped_strings
                         if s.strip() and not re.match(r"^\d+\s*[smhdw]", s.strip())), "")
        if not name or len(name) > 200:
            raise ValueError("Missing or invalid leaderboard participant")
        rows.append({"rank": int(rank_match.group(1)), "participant": name,
                     "score": float(score_cell.get_text(strip=True))})
    if not rows or min(r["rank"] for r in rows) != 1 or len({r["rank"] for r in rows}) != len(rows):
        raise ValueError("Leaderboard lacks a unique rank-one row")
    rows.sort(key=lambda r: r["rank"])
    if any(a["score"] < b["score"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Leaderboard is not descending by score")
    return rows


def retrieve(source: dict) -> dict:
    url = source["url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Source URL must be public HTTPS without embedded credentials")
    with requests.get(url, headers={"User-Agent": "Riftline-GEMS3-source-audit/1.0"},
                      timeout=(12, 35), stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_SOURCE_BYTES:
                raise ValueError("Source exceeds documented audit size bound")
        final_url = response.url
        if urlparse(final_url).scheme != "https":
            raise ValueError("Source redirected away from HTTPS")
        raw = bytes(data)
        status = response.status_code
    if source["id"] == "data-tab":
        if "/accounts/login/" not in final_url:
            raise ValueError("Data-tab access behavior changed; review canonical download access")
        return {"status": "authentication-required", "http_status": status, "final_url": final_url,
                "raw_sha256": hashlib.sha256(raw).hexdigest(), "checks": []}
    if "/accounts/login/" in final_url:
        raise ValueError("Unexpected authentication redirect")
    text = source_text(raw, parsed.path.lower().endswith(".pdf"))
    norm = normalized(text)
    checks = [{"claim_id": c["id"], "matched": normalized(c["quote"]) in norm,
               "quote": c["quote"]} for c in source["claims"]]
    result = {"status": "verified" if all(c["matched"] for c in checks) else "review-required",
              "http_status": status, "final_url": final_url,
              "raw_sha256": hashlib.sha256(raw).hexdigest(),
              "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "checks": checks,
              "scope": "Exact normalized quote presence; not proof of every possible interpretation"}
    if source["id"] == "leaderboard":
        result["leaderboard_rows"] = parse_leaderboard(raw)
    return result


def refresh(feed: dict, sources: list[dict], *, getter=retrieve, now: str | None = None) -> dict:
    """Pure state merge: preserve valid history on timeout, parse error, HTTP error or quote drift."""
    now = now or utc_now()
    out = copy.deepcopy(feed)
    previous = {s["id"]: s for s in out.get("sources", [])}

    def fetch_one(source):
        record = copy.deepcopy(previous.get(source["id"], {"id": source["id"], "last_verified_at": None}))
        record.update({"id": source["id"], "url": source["url"], "title": source["title"],
                       "last_attempt_at": now, "attempt_method": "scheduled HTTPS / normalized quote checks"})
        try:
            result = getter(source)
            old_hash = record.get("raw_sha256")
            record["content_changed"] = bool(old_hash and old_hash != result.get("raw_sha256"))
            record.update(result)
            record["last_retrieved_at"] = now
            record["error"] = None
            if result["status"] in {"verified", "authentication-required"}:
                record["last_verified_at"] = now
                record["verification_method"] = "HTTPS bytes, structural parsing / exact normalized quotes"
        except Exception as exc:
            record["status"] = "refresh-unavailable"
            record["error"] = f"{type(exc).__name__}: {exc}"[:600]
        age = age_hours(record.get("last_verified_at"), now)
        record["stale"] = age is None or age > STALE_HOURS
        return record

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch_one, sources))
    out.update({"schema_version": 1, "generated_at": now, "last_refresh_attempt_at": now,
                "stale_after_hours": STALE_HOURS, "sources": records,
                "automation": "Every 6 hours in GitHub Actions when enabled; schedules may be delayed. No browser scraping."})
    board = next((r for r in records if r["id"] == "leaderboard"), None)
    if board and board["status"] == "verified" and board.get("leaderboard_rows"):
        rows = board["leaderboard_rows"]
        out["leaderboard"] = {"verified_at": now, "source": board["url"], "rows": rows,
                               "leader": rows[0], "tracked_user": next((r for r in rows if r["participant"] == "extradr19"), None),
                               "artifact_mapping": "unknown; user score does not identify our candidate file"}
        point = {"checked_at": now, "leader": rows[0]["score"],
                 "extradr19": out["leaderboard"]["tracked_user"]["score"] if out["leaderboard"]["tracked_user"] else None}
        history = out.get("score_history", [])
        if not history or (point["leader"], point["extradr19"]) != (history[-1]["leader"], history[-1]["extradr19"]):
            history.append(point)
        out["score_history"] = history[-100:]
    out["alerts"] = [{"source_id": r["id"], "status": r["status"], "stale": r["stale"],
                      "detail": r.get("error") or "Quote/source freshness needs review"}
                     for r in records if r["status"] in {"review-required", "refresh-unavailable"} or r["stale"]]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=ROOT / "docs/data/feed.json")
    args = ap.parse_args()
    sources = read_json(ROOT / "research/sources.json")["sources"]
    existing = read_json(args.output) if args.output.exists() else {}
    report = refresh(existing, sources)
    write_json(args.output, report)
    print(f"Refreshed {len(sources)} sources; {len(report['alerts'])} explicit alerts. "
          "Failed sources retained last successful evidence.")


if __name__ == "__main__":
    main()
