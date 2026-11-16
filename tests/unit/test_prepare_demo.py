import json
from uuid import UUID

import pytest

from medassistmultimodal.prepare_demo import prepare_demo
from medassistmultimodal.infrastructure.structured_workspace import StructuredWorkspace
from medassistmultimodal.infrastructure.desktop_summary import SummaryService


def test_new_clone_can_run_synthetic_workflow_without_media(tmp_path):
    manifest = prepare_demo(tmp_path)
    workspace = StructuredWorkspace(tmp_path)
    assert manifest['model_calls'] == 0
    assert set(manifest['sessions']) == {'V01', 'V02', 'E01', 'E02', 'E03'}
    for sid in manifest['sessions'].values():
        detail = workspace.reader.detail(manifest['database'], UUID(sid)).document
        assert detail['integrity'] == 'verified'
        assert all(e['event']['review_status'] == 'pending_review' for e in detail['events'])
    assert workspace.register_scenario(manifest['database'], 'PAT-001', 'prescriptions', 'P06').persisted
    snapshot = SummaryService(tmp_path).build(manifest['database'], 'PAT-001', list(manifest['sessions'].values()))
    assert len(snapshot.document['session_ids']) == 5
    assert not (tmp_path/'data/raw').exists()
    assert not (tmp_path/'reports/DAY_12_TASKS_04_05_2026-11-05.json').exists()


def test_repeated_preparation_preserves_previous_database(tmp_path):
    first = prepare_demo(tmp_path)
    original = (tmp_path/first['database']).read_bytes()
    second = prepare_demo(tmp_path)
    assert first['database'] != second['database']
    assert (tmp_path/first['database']).read_bytes() == original


def test_changed_generated_input_rejected_before_new_workspace(tmp_path):
    manifest = prepare_demo(tmp_path)
    source = tmp_path/'data/synthetic/prescriptions_v1/P06_input.json'
    source.write_text('{}', encoding='utf-8')
    parent = (tmp_path/manifest['database']).parent.parent
    before = set(parent.iterdir())
    with pytest.raises(ValueError):
        prepare_demo(tmp_path)
    assert set(parent.iterdir()) == before
    assert source.read_text(encoding='utf-8') == '{}'


def test_changed_manifest_not_silently_replaced(tmp_path):
    prepare_demo(tmp_path)
    path = tmp_path/'data/synthetic/vitals_v1/manifest.json'
    doc = json.loads(path.read_bytes())
    doc['files']['V02.json']['sha256'] = '0'*64
    path.write_text(json.dumps(doc), encoding='utf-8')
    with pytest.raises(ValueError):
        prepare_demo(tmp_path)
