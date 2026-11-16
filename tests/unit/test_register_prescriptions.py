from contextlib import closing
import json
import sqlite3
from unittest.mock import patch
from uuid import UUID

import pytest

from medassistmultimodal.application.register_prescriptions import prepare_prescriptions,register_prepared_prescriptions
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.demo.prescription_fixtures import build_prescription_cases
from medassistmultimodal.demo import prescriptions_cli as cli
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context

RUN=UUID('da12da12-0000-4000-8000-000000000006')


def prepared(case='P06'):
    return prepare_prescriptions(encode_json(build_prescription_cases()[0][case]),run_id=RUN,
        evidence_ref='data/interim/prescriptions/evidence.json')


@pytest.fixture
def db():
    with closing(sqlite3.connect(':memory:')) as conn:
        conn.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(conn)
        SQLitePatientRepository(conn).save(create_patient_context());conn.commit()
        yield conn


def counts(db):
    return tuple(db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
        ('multimodal_sessions','multimodal_events','audit_records'))


@pytest.mark.parametrize('case,event_count',[('P01',1),('P02',2),('P06',2),('P12',3),('P14',2),('P17',1)])
def test_adapt_persist_and_repeat(db,case,event_count):
    p=prepared(case);assert p==prepared(case)
    assert len(p.events)==event_count
    for e in p.events:
        e.validate_for_session(p.session)
        assert e.timestamp==p.session.started_at and not e.is_mock
        assert e.review_status=='pending_review' and e.confidence is None
        assert e.source=='synthetic-prescriptions-v1' and p.evidence_sha256 in e.evidence_ref
    use_case=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db))
    first=register_prepared_prescriptions(p,use_case,lambda:p.evidence)
    assert register_prepared_prescriptions(p,use_case,lambda:p.evidence)==first
    assert counts(db)==(1,event_count,1)


@pytest.mark.parametrize('failure',['missing','tampered','audit','second_event'])
def test_failure_and_rollback(db,failure):
    p=prepared();uow=SQLiteMultimodalUnitOfWork(db);case=RegisterMultimodalSession(uow)
    def read():
        if failure=='missing':raise FileNotFoundError('missing fixture')
        return b'changed' if failure=='tampered' else p.evidence
    if failure in ('missing','tampered'):
        with pytest.raises((FileNotFoundError,ValueError)):register_prepared_prescriptions(p,case,read)
    else:
        target=uow.audit if failure=='audit' else uow.events
        original=target.save;seen=[]
        def fail(value):
            seen.append(value)
            if failure=='audit' or len(seen)==2:raise sqlite3.OperationalError('fixture failure')
            return original(value)
        with patch.object(target,'save',side_effect=fail):
            with pytest.raises(sqlite3.OperationalError):register_prepared_prescriptions(p,case,read)
    assert counts(db)==(0,0,0)
    register_prepared_prescriptions(p,case,lambda:p.evidence)
    assert counts(db)==(1,2,1)


def test_run_conflict_and_review_preserved(db):
    p=prepared();case=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db))
    register_prepared_prescriptions(p,case,lambda:p.evidence)
    other=prepared('P04')
    with pytest.raises(ValueError):register_prepared_prescriptions(other,case,lambda:other.evidence)
    assert counts(db)==(1,2,1)
    db.execute("UPDATE multimodal_events SET review_status='reviewed' WHERE event_id=?",(str(p.events[0].event_id),));db.commit()
    with pytest.raises(ValueError):register_prepared_prescriptions(p,case,lambda:p.evidence)
    assert db.execute('SELECT review_status FROM multimodal_events WHERE event_id=?',(str(p.events[0].event_id),)).fetchone()[0]=='reviewed'


def test_cli_reopen_export_and_evidence_failures(tmp_path,capsys):
    with patch.object(cli,'ROOT',tmp_path):
        source=tmp_path/'data/interim/prescriptions/input.json';source.parent.mkdir(parents=True)
        source.write_bytes(encode_json(build_prescription_cases()[0]['P06']))
        args=['persist','--input','data/interim/prescriptions/input.json','--run-id',str(RUN)]
        assert cli.main(args)==0;r=json.loads(capsys.readouterr().out)
        assert cli.main(args+['--reuse-db'])==0;assert json.loads(capsys.readouterr().out)==r
        assert cli.main(['list'])==0;listed=json.loads(capsys.readouterr().out)
        assert len(listed['cases'][0]['events'])==2
        output='data/interim/prescriptions/export.json'
        assert cli.main(['export','--output',output])==0;capsys.readouterr()
        assert json.loads((tmp_path/output).read_bytes())==listed
        assert cli.main(['export','--output',output])==2;capsys.readouterr()
        evidence=tmp_path/r['evidence_ref'];original=evidence.read_bytes()
        evidence.write_bytes(b'tampered')
        assert cli.main(args+['--reuse-db'])==2;capsys.readouterr()
        assert evidence.read_bytes()==b'tampered'
        evidence.write_bytes(original);evidence.rename(evidence.with_suffix('.saved'))
        assert cli.main(args+['--reuse-db'])==2;capsys.readouterr()
        assert not evidence.exists()


@pytest.mark.parametrize('path',['_backup/x.json','data/interim/prescriptions/../x.json','.git/x.json','data/interim/vitals/x.json'])
def test_path_restrictions(path):
    with pytest.raises(ValueError):cli.safe_path(path,'interim/prescriptions','.json')


def test_invalid_snapshot_no_database_created(tmp_path,capsys):
    with patch.object(cli,'ROOT',tmp_path):
        source=tmp_path/'data/interim/prescriptions/input.json';source.parent.mkdir(parents=True)
        source.write_bytes(encode_json(build_prescription_cases()[0]['P21']))
        assert cli.main(['persist','--input','data/interim/prescriptions/input.json','--run-id',str(RUN)])==2
        assert not (tmp_path/cli.DEFAULT_DATABASE).exists()
