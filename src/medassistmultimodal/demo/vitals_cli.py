"""Local synthetic-vitals processing, SQLite query and JSON export CLI."""
import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
from uuid import UUID

from medassistmultimodal.application.patient_context import Patient, PatientContext
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_vitals import prepare_vitals, register_prepared_vitals
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from .persistence import _read, _json

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = 'data/interim/vitals/day11.sqlite3'


def safe_path(value: str, area: str, suffix: str) -> Path:
    path = Path(value)
    if any(p.casefold() in {'_backup', '.git', '..'} for p in path.parts):
        raise ValueError('Private or parent traversal path forbidden')
    path = path if path.is_absolute() else ROOT / path
    allowed = ROOT / 'data' / area
    if not path.is_relative_to(allowed) or path.suffix.lower() != suffix:
        raise ValueError(f'Use {suffix} under data/{area}')
    for part in reversed((path, *path.parents)):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Links and junctions forbidden')
    return path


def persist(input_path: Path, database: Path, run_id: UUID, *, reuse: bool) -> dict:
    # All paths at this public IO boundary are checked before any read/write.
    input_path = safe_path(str(input_path), 'synthetic', '.json')
    database = safe_path(str(database), 'interim/vitals', '.sqlite3')
    evidence = safe_path(str(database.parent / 'evidence' / f'{run_id}.json'), 'interim/vitals', '.json')
    prepared = prepare_vitals(input_path.read_bytes(), run_id=run_id,
                              evidence_ref=evidence.relative_to(ROOT).as_posix())
    if database.exists() and not reuse:
        raise ValueError('Database exists; use --reuse-db for an explicit retry/addition')
    database.parent.mkdir(parents=True, exist_ok=True)
    if not database.exists():
        with database.open('xb'):
            pass
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        initialize_multimodal_schema(db)
        uow = SQLiteMultimodalUnitOfWork(db)
        existing_session = uow.sessions.get_by_id(prepared.session.session_id)
        if existing_session is not None and not evidence.is_file():
            raise ValueError('Committed run has missing evidence; recovery must be explicit')
        evidence.parent.mkdir(parents=True, exist_ok=True)
        if evidence.exists():
            if evidence.read_bytes() != prepared.evidence:
                raise ValueError('Run evidence conflict; previous evidence preserved')
        else:
            with evidence.open('xb') as stream:
                stream.write(prepared.evidence)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        # Synthetic registry is a separate explicit prerequisite, not part of the session transaction.
        patients = SQLitePatientRepository(db)
        pid = prepared.session.subject.patient_id
        context = PatientContext(Patient(pid, 'Pessoa fictícia ' + pid,
                                          date(1970, 1, 1), 'not_specified', True), (), (), ())
        existing = patients.get_by_id(pid)
        if existing is not None and existing != context:
            raise ValueError('Existing synthetic patient context differs; preserved')
        if existing is None:
            with db:
                patients.save(context)
        audit = register_prepared_vitals(prepared, RegisterMultimodalSession(uow), evidence.read_bytes)
    return {'run_id':str(run_id), 'session_id':str(prepared.session.session_id),
            'events':len(prepared.events), 'audit_id':audit,
            'evidence_ref':evidence.relative_to(ROOT).as_posix(),
            'evidence_sha256':prepared.evidence_sha256, 'clinical_validation':False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('persist','list','export'):
        sub = subs.add_parser(command)
        sub.add_argument('--database', default=DEFAULT_DATABASE)
        if command == 'persist':
            sub.add_argument('--input', required=True)
            sub.add_argument('--run-id', required=True, type=UUID)
            sub.add_argument('--reuse-db', action='store_true')
        else:
            sub.add_argument('--session-id', type=UUID)
        if command == 'export':
            sub.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        database = safe_path(args.database, 'interim/vitals', '.sqlite3')
        if args.command == 'persist':
            payload = persist(safe_path(args.input,'synthetic','.json'), database,
                              args.run_id,reuse=args.reuse_db)
        else:
            payload = _read(database, args.session_id)
        text = json.dumps(payload,default=_json,ensure_ascii=False,indent=2,allow_nan=False) + '\n'
        if args.command == 'export':
            output = safe_path(args.output,'interim/vitals','.json')
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('x',encoding='utf-8') as stream:
                stream.write(text)
        print(text,end='')
        return 0
    except (ValueError,OSError,sqlite3.Error) as exc:
        print(f'Erro: {exc}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
