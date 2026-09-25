"""Small deterministic utilities shared by CLI, evidence and publication gates."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: str | Path, value: object) -> None:
    """Atomic, strict JSON. NaN/Infinity must never enter evidence or web manifests."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


MODEL_SOURCES = ["common.py", "data.py", "emission.py", "features.py", "metric.py", "raster.py", "train.py"]


def code_digest() -> str:
    """Model/data/validation code fingerprint, excluding unrelated site/feed rendering code."""
    h = hashlib.sha256()
    for name in MODEL_SOURCES:
        path = ROOT / "gems3" / name
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()
