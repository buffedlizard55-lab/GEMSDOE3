import hashlib

import pytest

import gems3.data as data
from gems3.common import write_json


def pinned(tmp_path, monkeypatch, *, split=True):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    whole = b"small-but-real-binary-data-for-stream-integrity"
    pieces = [whole[:17], whole[17:]] if split else [whole]
    entries = []
    for i, content in enumerate(pieces):
        name = f"part-{i}"
        (bridge / name).write_bytes(content)
        entries.append({"name": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    entry = {"name": "features", "canonical": "training_features.tif", "bytes": len(whole),
             "sha256": hashlib.sha256(whole).hexdigest(), "parts": entries}
    manifest = bridge / "manifest.json"
    write_json(manifest, {"files": [entry]})
    monkeypatch.setattr(data, "BRIDGE", bridge)
    monkeypatch.setattr(data, "MANIFEST", manifest)
    return bridge, whole


def test_local_segments_hash_checked_and_idempotent(tmp_path, monkeypatch):
    bridge, whole = pinned(tmp_path, monkeypatch)
    out = tmp_path / "out"
    first = data.download_data(out)
    assert (out / "training_features.tif").read_bytes() == whole
    (bridge / "part-0").unlink()
    second = data.download_data(out)
    assert first[0]["sha256"] == second[0]["sha256"]
    assert second[0]["method"] == "existing file rehashed"


def test_bad_segment_cannot_replace_canonical_file(tmp_path, monkeypatch):
    bridge, _ = pinned(tmp_path, monkeypatch)
    (bridge / "part-1").write_bytes(b"corrupted")
    out = tmp_path / "out"
    out.mkdir()
    dest = out / "training_features.tif"
    dest.write_bytes(b"old file left intact on failure")
    with pytest.raises(ValueError, match="mismatch"):
        data.download_data(out)
    assert dest.read_bytes() == b"old file left intact on failure"
    assert not list(out.glob("*.part"))


def test_network_html_response_rejected(tmp_path, monkeypatch):
    bridge, _ = pinned(tmp_path, monkeypatch)
    (bridge / "part-0").unlink()

    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, _):
            yield b"<html>login</html>"

        def close(self):
            pass

    monkeypatch.setattr(data.requests, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError):
        data.download_data(tmp_path / "out")
    assert not (tmp_path / "out/training_features.tif").exists()


def test_original_import_manifest_preserves_all_small_blobs():
    from gems3.common import ROOT, read_json
    report = read_json(ROOT / "provenance/import.json")
    assert report["verified_git_blobs"] == 387 and report["missing"] == report["mismatched"] == []
    tree = read_json(ROOT / "provenance/upstream-tree.json")["tree"]
    excluded = set(report["excluded_from_new_git"])
    for entry in tree:
        if entry["type"] != "blob" or entry["path"] in excluded:
            continue
        relative = ".gitignore.upstream" if entry["path"] == ".gitignore" else entry["path"]
        path = ROOT / "legacy" / relative
        raw = path.read_bytes()
        assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == entry["sha"]


def test_configured_github_fallback_is_still_hash_gated(tmp_path, monkeypatch):
    from types import SimpleNamespace
    bridge, whole = pinned(tmp_path, monkeypatch)
    first = (bridge/'part-0').read_bytes()
    (bridge/'part-0').unlink()

    def blocked(*args, **kwargs):
        raise data.requests.exceptions.SSLError('controlled raw-host failure')

    def successful_gh(args, **kwargs):
        assert args[:2] == ['gh', 'api'] and data.UPSTREAM_COMMIT in args[-1]
        kwargs['stdout'].write(first)
        return SimpleNamespace(returncode=0, stderr=b'')

    monkeypatch.setattr(data.requests, 'get', blocked)
    monkeypatch.setattr(data.shutil, 'which', lambda _: '/usr/bin/gh')
    monkeypatch.setattr(data.subprocess, 'run', successful_gh)
    data.download_data(tmp_path/'out')
    assert (tmp_path/'out/training_features.tif').read_bytes() == whole
    assert not list((tmp_path/'out').glob('*.segment'))


def test_auth_failure_never_installs_an_error_as_a_raster(tmp_path, monkeypatch):
    from types import SimpleNamespace
    bridge, _ = pinned(tmp_path, monkeypatch)
    (bridge/'part-0').unlink()

    def blocked(*args, **kwargs):
        raise data.requests.exceptions.SSLError('controlled raw-host failure')

    monkeypatch.setattr(data.requests, 'get', blocked)
    monkeypatch.setattr(data.shutil, 'which', lambda _: '/usr/bin/gh')
    monkeypatch.setattr(data.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1, stderr=b'Bad credentials (HTTP 401)'))
    with pytest.raises(RuntimeError, match='Bad credentials'):
        data.download_data(tmp_path/'out')
    assert not (tmp_path/'out/training_features.tif').exists()
    assert not list((tmp_path/'out').glob('*.segment'))
    assert not list((tmp_path/'out').glob('*.part'))
