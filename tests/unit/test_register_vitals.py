from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import UUID

import pytest

from medassistmultimodal.demo.synthetic_vitals import build_scenarios,json_bytes
from medassistmultimodal.demo import vitals_cli
from medassistmultimodal.application.register_vitals import prepare_vitals,register_prepared_vitals,strict_json
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context

RUN = UUID('bccf4000-409d-4c8c-bdf4-000000000002')


def prepared(number=2,run=RUN):
    return prepare_vitals(json_bytes(build_scenarios()[0][number-1]),run_id=run,evidence_ref='data/interim/vitals/evidence.json')


@pytest.fixture
def db():
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        initialize_multimodal_schema(connection)
        SQLitePatientRepository(connection).save(create_patient_context())
        connection.commit()
        yield connection


def counts(db):
    return tuple(db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                 for table in ('multimodal_sessions','multimodal_events','audit_records'))


def test_adaptation_timestamp_evidence_origin_and_stable_ids():
    p=prepared()
    assert p==prepared() and p.session.session_id!=prepared(run=UUID(int=32)).session.session_id
    assert len(p.events)==2
    assert p.events[1].timestamp.second==5
    assert hashlib.sha256(p.evidence).hexdigest()==p.evidence_sha256
    for event in p.events:
        event.validate_for_session(p.session)
        assert not event.is_mock and event.confidence is None
        assert event.review_status=='pending_review' and event.patient_id=='PAT-001'
        assert event.source_kind=='synthetic' and p.evidence_sha256 in event.evidence_ref


@pytest.mark.parametrize('number,events',[(1,1),(2,2),(12,5),(18,3)])
def test_actual_results_persist_and_retry_without_duplicates(db,number,events):
    p=prepared(number)
    use_case=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db))
    first=register_prepared_vitals(p,use_case,lambda:p.evidence)
    assert register_prepared_vitals(p,use_case,lambda:p.evidence)==first
    assert counts(db)==(1,events,1)


@pytest.mark.parametrize('failure',['missing','different'])
def test_evidence_failure_before_writes(db,failure):
    p=prepared()
    def read():
        if failure=='missing':raise FileNotFoundError('missing')
        return b'changed'
    with pytest.raises((ValueError,FileNotFoundError)):
        register_prepared_vitals(p,RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db)),read)
    assert counts(db)==(0,0,0)


def test_audit_failure_rolls_back_and_same_evidence_recovers(db):
    p=prepared()
    uow=SQLiteMultimodalUnitOfWork(db)
    case=RegisterMultimodalSession(uow)
    with patch.object(uow.audit,'save',side_effect=sqlite3.OperationalError('unavailable')):
        with pytest.raises(sqlite3.OperationalError): register_prepared_vitals(p,case,lambda:p.evidence)
    assert counts(db)==(0,0,0)
    register_prepared_vitals(p,case,lambda:p.evidence)
    assert counts(db)==(1,2,1)


def test_same_run_different_input_conflicts_atomically(db):
    p=prepared()
    case=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db))
    register_prepared_vitals(p,case,lambda:p.evidence)
    altered=prepared(3)
    with pytest.raises(ValueError): register_prepared_vitals(altered,case,lambda:altered.evidence)
    assert counts(db)==(1,2,1)


def test_second_event_failure_rolls_back(db):
    p=prepared()
    uow=SQLiteMultimodalUnitOfWork(db)
    save=uow.events.save
    seen=[]
    def fail_second(event):
        seen.append(event)
        if len(seen)==2:raise sqlite3.OperationalError('second event failure')
        save(event)
    with patch.object(uow.events,'save',side_effect=fail_second):
        with pytest.raises(sqlite3.OperationalError):
            register_prepared_vitals(p,RegisterMultimodalSession(uow),lambda:p.evidence)
    assert counts(db)==(0,0,0)


@pytest.mark.parametrize('data',[b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":Infinity}'])
def test_strict_input_json(data):
    with pytest.raises(ValueError):strict_json(data)


@pytest.mark.parametrize('path',['_backup/file.json','data/interim/vitals/../file.json',
    'data/interim/demo/file.json','.git/file.json'])
def test_cli_rejects_private_or_outside_paths(path):
    with pytest.raises(ValueError):vitals_cli.safe_path(path,'interim/vitals','.json')


def test_cli_persist_reopen_query_export_and_missing_evidence(tmp_path,capsys):
    with patch.object(vitals_cli,'ROOT',tmp_path):
        source=tmp_path/'data/synthetic/input.json'
        source.parent.mkdir(parents=True)
        source.write_bytes(json_bytes(build_scenarios()[0][1]))
        args=['persist','--input','data/synthetic/input.json','--run-id',str(RUN)]
        assert vitals_cli.main(args)==0
        first=json.loads(capsys.readouterr().out)
        assert vitals_cli.main(args+['--reuse-db'])==0
        assert json.loads(capsys.readouterr().out)==first
        assert vitals_cli.main(['list'])==0
        listed=json.loads(capsys.readouterr().out)
        assert len(listed['cases'])==1 and len(listed['cases'][0]['events'])==2
        output='data/interim/vitals/export.json'
        assert vitals_cli.main(['export','--output',output])==0
        capsys.readouterr()
        assert json.loads((tmp_path/output).read_text(encoding='utf-8'))==listed
        assert vitals_cli.main(['export','--output',output])==2
        capsys.readouterr()
        evidence=tmp_path/first['evidence_ref']
        # Rename preserves the artifact, while simulating loss at the expected location.
        evidence.rename(evidence.with_suffix('.saved'))
        assert vitals_cli.main(args+['--reuse-db'])==2
        assert not evidence.exists()


def test_cli_changed_input_preserves_evidence_and_database(tmp_path,capsys):
    with patch.object(vitals_cli,'ROOT',tmp_path):
        source=tmp_path/'data/synthetic/input.json'
        source.parent.mkdir(parents=True)
        source.write_bytes(json_bytes(build_scenarios()[0][1]))
        args=['persist','--input','data/synthetic/input.json','--run-id',str(RUN)]
        assert vitals_cli.main(args)==0
        first=json.loads(capsys.readouterr().out)
        evidence=tmp_path/first['evidence_ref']
        before=evidence.read_bytes()
        source.write_bytes(json_bytes(build_scenarios()[0][2]))
        assert vitals_cli.main(args+['--reuse-db'])==2
        assert evidence.read_bytes()==before
        with closing(sqlite3.connect(tmp_path/vitals_cli.DEFAULT_DATABASE)) as conn:
            assert counts(conn)==(1,2,1)


def test_retry_does_not_reset_review_status(db):
    p=prepared()
    case=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db))
    register_prepared_vitals(p,case,lambda:p.evidence)
    # Simulated future human review state, not a production review workflow.
    db.execute("UPDATE multimodal_events SET review_status='reviewed' WHERE event_id=?",
               (str(p.events[0].event_id),))
    db.commit()
    with pytest.raises(ValueError):register_prepared_vitals(p,case,lambda:p.evidence)
    assert db.execute('SELECT review_status FROM multimodal_events WHERE event_id=?',
                      (str(p.events[0].event_id),)).fetchone()[0]=='reviewed'
    assert counts(db)==(1,2,1)


def test_cli_tampered_evidence_blocks_retry(tmp_path,capsys):
    with patch.object(vitals_cli,'ROOT',tmp_path):
        source=tmp_path/'data/synthetic/input.json'
        source.parent.mkdir(parents=True)
        source.write_bytes(json_bytes(build_scenarios()[0][1]))
        args=['persist','--input','data/synthetic/input.json','--run-id',str(RUN)]
        assert vitals_cli.main(args)==0
        first=json.loads(capsys.readouterr().out)
        evidence=tmp_path/first['evidence_ref']
        evidence.write_bytes(b'tampered fixture')
        assert vitals_cli.main(args+['--reuse-db'])==2
        assert evidence.read_bytes()==b'tampered fixture'
        with closing(sqlite3.connect(tmp_path/vitals_cli.DEFAULT_DATABASE)) as conn:
            assert counts(conn)==(1,2,1)
