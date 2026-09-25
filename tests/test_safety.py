import hashlib
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from affine import Affine

from gems3.common import ROOT, read_json
from gems3.emission import emit
from gems3.features import build_features
from gems3.infer import infer
from gems3.metric import MetricContext
from scripts import stage_site


@pytest.mark.parametrize('bad', [-1, 0.25, 2, np.nan, np.inf])
def test_nodata_or_probabilities_are_not_silently_promoted_to_truth(bad):
    a = np.zeros((5, 6))
    a[2, 2] = bad
    with pytest.raises(ValueError, match='binary'):
        MetricContext(a)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -0.01, 1.01])
def test_cached_ridges_cannot_bypass_prediction_validation(bad):
    a = np.zeros((15, 15), dtype='float32')
    a[7, 7] = bad
    with pytest.raises(ValueError):
        emit(a, np.ones_like(a, bool), 0.2, 'soft-ridge', np.ones_like(a, bool))


def test_cached_ridge_shape_and_type_are_validated():
    a = np.zeros((15, 15), dtype='float32')
    with pytest.raises(ValueError, match='boolean'):
        emit(a, np.ones_like(a, bool), 0.2, 'soft-ridge', np.ones((15, 15), 'float32'))
    with pytest.raises(ValueError, match='boolean'):
        emit(a, np.ones_like(a, bool), 0.2, 'soft-ridge', np.ones((3, 3), bool))


@pytest.mark.parametrize('target', ['.', '.git', '.git/new', 'docs', 'build', '../outside'])
def test_staging_refuses_root_git_source_and_outside_paths(target):
    with pytest.raises(ValueError):
        stage_site.stage(ROOT / target)


def test_staging_refuses_symlinked_destination(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'build').mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'build/site').symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(stage_site, 'ROOT', root)
    with pytest.raises(ValueError, match='symlink'):
        stage_site.stage(root / 'build/site')


def test_staging_cleans_only_its_whitelisted_public_subtrees(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    (root / 'docs').mkdir(parents=True)
    (root / 'docs/index.html').write_text('current')
    (root / 'build/site/docs').mkdir(parents=True)
    (root / 'build/site/docs/obsolete.html').write_text('stale')
    (root / '.git').mkdir()
    (root / '.git/config').write_text('private configuration sentinel')
    monkeypatch.setattr(stage_site, 'ROOT', root)
    stage_site.stage(root / 'build/site')
    assert not (root / 'build/site/docs/obsolete.html').exists()
    assert not (root / 'build/site/.git').exists()
    assert (root / '.git/config').read_text() == 'private configuration sentinel'


def test_features_cache_binds_input_mask_config_and_implementation(tmp_path, monkeypatch):
    import gems3.features as module
    path = tmp_path / 'features.tif'
    rng = np.random.default_rng(3)
    a = rng.normal(size=(19, 21, 22)).astype('float32')
    a[:, :2] = -3.4028235e38
    with rasterio.open(path, 'w', driver='GTiff', count=19, height=21, width=22, dtype='float32',
                       crs='EPSG:32611', transform=Affine(100, 0, 200000, 0, -100, 4500000),
                       nodata=-3.4028235e38) as dst:
        dst.write(a)
    valid = np.ones((21, 22), bool)
    config = {'buffer_px': 8, 'derived_bands': [12], 'scales_px': [1]}
    first, ids, meta = build_features(path, valid, tmp_path/'cache', config)
    assert first.shape == (valid.size, 23)
    assert meta['config']['implementation_sha256']
    again, _, cached = build_features(path, valid, tmp_path/'cache', config)
    assert cached == meta
    np.testing.assert_allclose(first, again, equal_nan=True)
    old_hash = module.sha256
    monkeypatch.setattr(module, 'sha256', lambda p: 'new-implementation' if Path(p) == Path(module.__file__) else old_hash(p))
    _, _, changed = build_features(path, valid, tmp_path/'cache', config)
    assert changed['key'] != meta['key']
    assert changed['config']['implementation_sha256'] == 'new-implementation'


def test_inference_refuses_untrusted_model_before_loading_pickle(tmp_path):
    model = tmp_path / 'bad.joblib'
    model.write_bytes(b'not a model')
    report = tmp_path / 'report.json'
    report.write_text('{"final_model_sha256":"not-the-file-hash"}')
    with pytest.raises(ValueError, match='refusing deserialization'):
        infer(tmp_path/'features.tif', tmp_path/'template.tif', model, report, tmp_path/'out.tif')
    assert not (tmp_path/'out.tif').exists()


def test_archived_training_code_matches_the_executed_report_not_a_future_edit():
    provenance = read_json(ROOT/'provenance/model-source.json')
    report = read_json(ROOT/'docs/data/experiment.json')
    h = hashlib.sha256()
    for item in provenance['files']:
        data = (ROOT / provenance['bundle'] / item['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        h.update(item['file'].encode())
        h.update(data)
    assert h.hexdigest() == provenance['code_sha256']
    # This bundle identifies the released run. Future rerun artifacts may use a newer source
    # fingerprint; matching is required for this committed published candidate identity.
    assert provenance['code_sha256'] == report['code_sha256']


def test_workflows_do_not_write_to_main_and_deployment_has_real_gates():
    workflows = list((ROOT / '.github/workflows').glob('*.yml'))
    assert len(workflows) == 3
    for path in workflows:
        text = path.read_text()
        wf = yaml.load(text, Loader=yaml.BaseLoader)
        assert wf['permissions']['contents'] == 'read'
        assert 'git push' not in text
        assert all('timeout-minutes' in j for j in wf['jobs'].values())
    feed = (ROOT / '.github/workflows/source-feed-pages.yml').read_text()
    assert 'python scripts/check_published.py' in feed
    assert 'actions/deploy-pages' in feed
    assert 'push:' not in feed.split('permissions:')[0]  # avoid legacy Pages deployment race
